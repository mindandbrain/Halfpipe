# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import re
from argparse import Namespace
from collections import OrderedDict, defaultdict
from copy import deepcopy
from fnmatch import fnmatch
from functools import partial
from pathlib import Path
from shutil import copyfile, rmtree
from typing import Mapping

import networkx as nx
import nipype.pipeline.engine as pe
from nipype.interfaces import utility as niu
from nipype.interfaces.base.support import InterfaceResult
from nipype.pipeline.engine.utils import merge_dict

from ..fixes import Node
from ..logging import logger
from ..resource import get as getresource
from ..utils.cache import cache_obj, uncache_obj
from ..utils.format import format_like_bids, normalize_subject
from ..utils.path import resolve
from ..utils.table import SynchronizedTable
from .base import IdentifiableWorkflow
from .constants import Constants

max_chunk_size = 50  # subjects


class IdentifiableDiGraph(nx.DiGraph):
    uuid: str | None


def filter_subjects(subjects: list[str], opts: Namespace) -> list[str]:
    subjects = sorted(subjects)

    try:
        subjects.remove("model")
    except ValueError:
        pass

    for pattern in opts.subject_exclude:
        subjects = [n for n in subjects if not fnmatch(n, pattern) and not fnmatch(format_like_bids(n), pattern)]

    for pattern in opts.subject_include:
        subjects = [n for n in subjects if fnmatch(n, pattern) or fnmatch(format_like_bids(n), pattern)]

    if opts.subject_list is not None:
        subject_list_path = resolve(opts.subject_list, opts.fs_root)

        with open(subject_list_path) as file_handle:
            subject_set = set(s.strip() for s in file_handle.readlines())

        subject_set |= set(map(normalize_subject, subject_set))
        subject_set |= set(map(format_like_bids, subject_set))

        subjects = [subject for subject in subjects if subject in subject_set or format_like_bids(subject) in subject_set]

    return subjects


def extract_subject_name(hierarchy):
    m = re.fullmatch(r"sub_(?P<subjectname>.+)_wf", hierarchy[2])
    if m is not None:
        return m.group("subjectname")


def node_result_file(u: pe.Node) -> Path:
    u._output_dir = None  # reset this just in case

    output_dir = u.output_dir()
    assert isinstance(output_dir, str)

    result_file = Path(output_dir) / f"result_{u.name}.pklz"

    return result_file


def find_input_source(graph: nx.DiGraph, u: Node, v: Node, c: dict):
    stack = [(u, v, source_info, field) for source_info, field in c["connect"]]

    result = list()

    while len(stack) > 0:
        node, v, source_info, field = stack.pop(0)
        if not isinstance(node.interface, niu.IdentityInterface):
            result.append((node, v, source_info, field))
            continue
        assert not isinstance(source_info, tuple)
        for in_edge in graph.in_edges(node, data=True):
            assert len(in_edge) == 3
            u, _, k = in_edge
            assert isinstance(k, dict)
            for u_source_info, node_field in k["connect"]:
                if source_info == node_field:
                    stack.append((u, v, u_source_info, field))

    stack = result
    result = list()

    while len(stack) > 0:
        u, node, source_info, field = stack.pop(0)
        if not isinstance(node.interface, niu.IdentityInterface):
            result.append((u, node, source_info, field))
            continue
        for out_edge in graph.out_edges(node, data=True):
            assert len(out_edge) == 3
            _, v, k = out_edge
            assert isinstance(k, dict)
            for node_source_info, v_field in k["connect"]:
                if node_source_info == field:
                    stack.append((u, v, source_info, v_field))

    input_source_dict: dict[pe.Node, dict] = defaultdict(dict)
    for u, v, source_info, field in result:
        u.keep = True  # don't allow results to be deleted

        input_source_dict[v][field] = (node_result_file(u), source_info)

    return input_source_dict


def resolve_input_boundary(flat_graph, non_subject_nodes) -> None:
    pre_run_result_dict: dict[pe.Node, InterfaceResult] = dict()
    for u, v, c in nx.edge_boundary(flat_graph, non_subject_nodes, data=True):  # type: ignore
        if u not in pre_run_result_dict:
            pre_run_result_dict[u] = u.run()

        connections = c["connect"]
        result = pre_run_result_dict[u]
        assert result.outputs is not None

        for u_field, v_field in connections:
            if isinstance(u_field, tuple):
                raise NotImplementedError()

            value = result.outputs.trait_get()[u_field]
            v.set_input(v_field, value)

    for u in pre_run_result_dict.keys():
        rmtree(u.output_dir(), ignore_errors=True)
        flat_graph.remove_node(u)

    assert len(nx.node_boundary(flat_graph, non_subject_nodes)) == 0  # type: ignore


def resolve_output_boundary(flat_graph, non_subject_nodes) -> dict[str, dict]:
    input_source_dict: dict[str, dict] = defaultdict(dict)

    for v, u, c in nx.edge_boundary(  # type: ignore
        flat_graph.reverse(), non_subject_nodes, data=True
    ):
        edge_input_source_dict = find_input_source(flat_graph, u, v, c)

        for v, input_sources in edge_input_source_dict.items():
            fullname = v.fullname
            assert isinstance(fullname, str)
            input_source_dict[fullname].update(input_sources)

    return input_source_dict


def split_flat_graph(flat_graph: nx.DiGraph, base_dir: str) -> tuple[dict[str, set[pe.Node]], dict[str, dict]]:
    subject_nodes: dict[str, set[pe.Node]] = defaultdict(set)
    for node in flat_graph:
        node.base_dir = base_dir  # make sure to use correct base path

        hierarchy = node._hierarchy.split(".")

        if len(hierarchy) < 3:
            continue

        subject_name = extract_subject_name(hierarchy)
        if subject_name is not None:
            subject_nodes[subject_name].add(node)

    all_subject_nodes = set().union(*subject_nodes.values())
    non_subject_nodes = set(flat_graph.nodes) - all_subject_nodes

    resolve_input_boundary(flat_graph, non_subject_nodes)
    input_source_dict = resolve_output_boundary(flat_graph, non_subject_nodes)

    return subject_nodes, input_source_dict


def prepare_graph(config, base_dir, uuid, graph):
    graph = pe.generate_expanded_graph(graph)

    for index, node in enumerate(graph):
        node.config = merge_dict(deepcopy(config), node.config)
        node.base_dir = base_dir
        node.index = index

    empty_workflow = pe.Workflow(name="empty")
    empty_workflow._configure_exec_nodes(graph)  # self is not accessed
    graph.uuid = uuid

    return graph


def init_flat_graph(workflow, workdir) -> nx.DiGraph:
    flat_graph = uncache_obj(workdir, ".flat_graph", workflow.uuid, display_str="flat graph")
    if flat_graph is not None:
        assert isinstance(flat_graph, nx.DiGraph)
        return flat_graph

    workflow._generate_flatgraph()
    flat_graph = workflow._graph

    cache_obj(workdir, ".flat_graph", flat_graph, uuid=workflow.uuid)
    return flat_graph


def init_execgraph(workdir: Path | str, workflow: IdentifiableWorkflow) -> dict[str, IdentifiableDiGraph]:
    uuid = workflow.uuid
    assert uuid is not None
    uuidstr = str(uuid)[:8]

    # init reports

    reports_directory = Path(workdir) / "reports"
    reports_directory.mkdir(parents=True, exist_ok=True)

    indexhtml_path = reports_directory / "index.html"
    copyfile(getresource("index.html"), indexhtml_path)

    for ftype in ["imgs", "vals", "preproc", "error"]:
        report_fname = reports_directory / f"report{ftype}.js"
        with SynchronizedTable(report_fname) as dlf:
            dlf.is_dirty = True  # force write

    # init dirs

    modeldir = Path(workdir) / Constants.workflow_directory / "models_wf"
    modeldir.mkdir(parents=True, exist_ok=True)

    # create or load execgraph

    graphs: dict[str, IdentifiableDiGraph] = dict()

    obj = uncache_obj(workdir, "graphs", uuid)
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            assert isinstance(v, IdentifiableDiGraph)
            graphs[k] = v

        if len(graphs) > 0:
            return graphs
        else:
            logger.warning("Re-generating invalid graphs")
            graphs = dict()

    logger.info("Generating flat graph")

    flat_graph = init_flat_graph(workflow, workdir)

    logger.info("Set needed outputs per node")

    workflow._set_needed_outputs(flat_graph)

    logger.info("Splitting graph")

    base_dir = str(workflow.base_dir)
    subject_nodes, input_source_dict = split_flat_graph(flat_graph, base_dir)

    graphs = OrderedDict()
    for s, nodes in sorted(subject_nodes.items(), key=lambda t: t[0]):
        s = workflow.bids_to_sub_id_map.get(s, s)

        if s == "model":
            raise ValueError('Subject cannot be named "model"')

        subgraph: nx.DiGraph = flat_graph.subgraph(nodes).copy()
        graphs[s] = IdentifiableDiGraph(subgraph)

        flat_graph.remove_nodes_from(nodes)

    if len(flat_graph.nodes) > 0:
        graphs["model"] = IdentifiableDiGraph(flat_graph)

    logger.info("Expanding subgraphs")

    partial_prepare_graph = partial(prepare_graph, workflow.config, workflow.base_dir, uuid)
    for s, graph in graphs.items():
        graphs[s] = partial_prepare_graph(graph)

    logger.info("Update input source at chunk boundaries")

    for graph in graphs.values():
        for node in graph:
            fullname = node.fullname
            if fullname in input_source_dict:
                node.input_source.update(input_source_dict[fullname])

    logger.info(f'Created graphs for workflow "{uuidstr}"')
    cache_obj(workdir, "graphs", graphs, uuid=uuid)

    return graphs
