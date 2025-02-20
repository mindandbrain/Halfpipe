# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import logging
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("halfpipe")


def run_stage_ui(opts: Namespace) -> None:
    from ..ui import init_spec_ui
    from ..ui.components.config import Config as UIConfig

    UIConfig.fs_root = str(opts.fs_root)
    opts.workdir = init_spec_ui(workdir=opts.workdir, debug=opts.debug)


def run_stage_workflow(opts):
    from fmriprep import config

    if opts.nipype_omp_nthreads is not None and opts.nipype_omp_nthreads > 0:
        config.nipype.omp_nthreads = opts.nipype_omp_nthreads  # type: ignore
        omp_nthreads_origin = "command line arguments"

    elif opts.use_cluster:
        config.nipype.omp_nthreads = 2
        omp_nthreads_origin = "from --use-cluster"

    else:
        omp_nthreads = opts.nipype_n_procs // 4
        if omp_nthreads < 1:
            omp_nthreads = 1
        if omp_nthreads > 8:
            omp_nthreads = 8
        config.nipype.omp_nthreads = omp_nthreads

        omp_nthreads_origin = "inferred"

    logger.info(f"config.nipype.omp_nthreads={config.nipype.omp_nthreads} ({omp_nthreads_origin})")

    from ..workflows.base import init_workflow
    from ..workflows.execgraph import init_execgraph

    workflow = init_workflow(opts.workdir)

    if workflow is None:
        return None

    opts.graphs = init_execgraph(opts.workdir, workflow)

    if opts.graphs is None:
        return

    if opts.use_cluster:
        from ..cluster import make_script

        make_script(opts.workdir, opts.graphs, opts)


def run_stage_run(opts: Namespace):
    from math import ceil

    import networkx as nx
    import numpy as np

    from ..utils.path import resolve

    workdir: Path = opts.workdir

    if opts.graphs is not None:
        graphs: Mapping[str, Any] = opts.graphs
        logger.info("Using graphs from previous step")

    else:
        if opts.graphs_file is not None:
            from ..utils.pickle import load_pickle

            fs_root = Path(opts.fs_root)
            graphs_file = str(resolve(opts.graphs_file, fs_root))

            logger.info(f'Using graphs defined in file "{graphs_file}"')

            obj = load_pickle(graphs_file)
            if not isinstance(obj, Mapping):
                raise ValueError(f'Invalid graphs file "{graphs_file}"')

            graphs = obj

        elif opts.uuid is not None:
            from ..utils.cache import uncache_obj

            obj = uncache_obj(workdir, type_str="graphs", uuid=opts.uuid)
            if not isinstance(obj, Mapping):
                raise ValueError(f'Could not find graphs for "{opts.uuid}"')

            graphs = obj

        else:
            raise RuntimeError('Please specify the uuid of the execution graphs to run using "--uuid"')

    if opts.nipype_resource_monitor is True:
        import nipype

        nipype.config.enable_resource_monitor()

    plugin_args: dict[str, Path | bool | float] = dict(
        workdir=workdir,
        watchdog=opts.watchdog,
        stop_on_first_crash=opts.debug,
        resource_monitor=opts.nipype_resource_monitor,
        raise_insufficient=False,
        keep=opts.keep,
    )

    if opts.nipype_n_procs is not None:
        plugin_args["n_procs"] = opts.nipype_n_procs

    if opts.nipype_memory_gb is not None:
        plugin_args["memory_gb"] = opts.nipype_memory_gb
    else:
        from ..memory import memory_limit

        memory_gb = memory_limit()
        if memory_gb is not None:
            plugin_args["memory_gb"] = memory_gb

    runnername = f"{opts.nipype_run_plugin}Plugin"

    import nipype.pipeline.plugins as nip

    import halfpipe.plugins as ppp

    if hasattr(ppp, runnername):
        logger.info(f'Using a patched version of nipype_run_plugin "{runnername}"')
        runnercls = getattr(ppp, runnername)

    elif hasattr(nip, runnername):
        logger.warning(f'Using unsupported nipype_run_plugin "{runnername}"')
        runnercls = getattr(nip, runnername)

    else:
        raise ValueError(f'Unknown nipype_run_plugin "{runnername}"')

    from pprint import pformat

    logger.debug(f"Using plugin arguments\n{pformat(plugin_args)}")

    from ..workflows.execgraph import filter_subjects

    chunks = list(graphs.keys())
    subjects = filter_subjects(chunks, opts)

    n_chunks = opts.n_chunks
    if n_chunks is None:
        if opts.subject_chunks or opts.use_cluster:
            n_chunks = len(subjects)
        else:
            n_chunks = ceil(len(subjects) / float(opts.max_chunk_size))

    index_arrays = np.array_split(np.arange(len(subjects)), n_chunks)

    if opts.only_chunk_index is not None:
        zero_based_chunk_index = opts.only_chunk_index - 1
        if zero_based_chunk_index >= n_chunks or zero_based_chunk_index < 0:
            logger.info(f"Not running chunk {opts.only_chunk_index} as is not defined")
            return

        logger.info(f"Will run subject level chunk {opts.only_chunk_index} of {n_chunks}")

        index_arrays = [index_arrays[zero_based_chunk_index]]

    elif opts.only_model_chunk:
        index_arrays = list()

    chunks_to_run: list[nx.DiGraph] = list()
    for index_array in index_arrays:
        graph_list = [graphs[subjects[i]] for i in index_array]
        chunks_to_run.append(
            nx.compose_all(graph_list)  # type: ignore
        )  # take len(index_array) subjects and compose

    if opts.only_chunk_index is not None:
        logger.info("Will not run model chunk")

    elif "model" in graphs:
        logger.info("Will run model chunk")

        chunks_to_run.append(graphs["model"])

    if len(chunks_to_run) == 0:
        raise ValueError("No graphs to run")

    from nipype.interfaces import freesurfer as fs

    if any(isinstance(node.interface, fs.FSCommand) for chunk in chunks_to_run for node in chunk.nodes):
        from niworkflows.utils.misc import check_valid_fs_license

        if not check_valid_fs_license():
            raise RuntimeError(
                "fMRIPrep needs to use FreeSurfer commands, but a valid license file for FreeSurfer could not be found. \n"
                "HALFpipe looked for an existing license file at several paths, in this order: \n"
                '1) a "license.txt" file in your HALFpipe working directory \n'
                '2) command line argument "--fs-license-file" \n'
                "Get it (for free) by registering at https://surfer.nmr.mgh.harvard.edu/registration.html"
            )

    from nipype.pipeline import engine as pe

    for i, chunk in enumerate(chunks_to_run):
        if len(chunks_to_run) > 1:
            logger.info(f"Running chunk {i + 1} of {len(chunks_to_run)}")

        try:
            assert isinstance(chunk, nx.DiGraph)

            runner = runnercls(plugin_args=plugin_args)
            firstnode = next(iter(chunk.nodes()))
            if firstnode is not None:
                assert isinstance(firstnode, pe.Node)
                logger.warning(f"Running chunk with {len(chunk.nodes())} nodes. First node: {firstnode.fullname}")
                runner.run(chunk, updatehash=False, config=firstnode.config)
        except Exception as e:
            if opts.debug:
                #! here is nice to have a set trace.
                raise e
            else:
                logger.warning(f"Ignoring exception in chunk {i + 1}", exc_info=True)

        if len(chunks_to_run) > 1:
            logger.info(f"Completed chunk {i + 1} of {len(chunks_to_run)}")


def run(opts, should_run):
    import os

    from ..utils.path import resolve

    if not opts.verbose:
        logger.log(
            25,
            'Option "--verbose" was not specified. Will not print detailed logs to the terminal. \n'
            'Detailed logs information will only be available in the "log.txt" file in the working directory. ',
        )

    logger.debug(f"debug={opts.debug}")

    logger.debug(f'should_run["spec-ui"]={should_run["spec-ui"]}')
    if should_run["spec-ui"]:
        logger.info("Stage: spec-ui")
        run_stage_ui(opts)
    else:
        logger.info("Loading existing spec")

    assert opts.workdir is not None, 'Missing working directory. Please specify using "--workdir"'
    assert Path(opts.workdir).is_dir(), "Working directory does not exist"

    if opts.fs_license_file is not None:
        fs_license_file = resolve(opts.fs_license_file, opts.fs_root)
        if fs_license_file.is_file():
            os.environ["FS_LICENSE"] = str(fs_license_file)
    else:
        from glob import glob

        license_files = list(glob(str(Path(opts.workdir) / "*license*")))

        if len(license_files) > 0:
            license_file = str(license_files[0])
            os.environ["FS_LICENSE"] = license_file

    if os.environ.get("FS_LICENSE") is not None:
        logger.debug(f'Using FreeSurfer license "{os.environ["FS_LICENSE"]}"')

    opts.graphs = None

    logger.debug(f'should_run["workflow"]={should_run["workflow"]}')
    if should_run["workflow"]:
        logger.info("Stage: workflow")
        run_stage_workflow(opts)

    logger.debug(f'should_run["run"]={should_run["run"]}')
    logger.debug(f"opts.use_cluster={opts.use_cluster}")

    if should_run["run"] and not opts.use_cluster:
        logger.info("Stage: run")
        run_stage_run(opts)


def main() -> None:
    # make these variables available in top scope
    opts: Namespace | None = None
    profiler_instance = None

    debug: bool = False
    profile: bool = False

    try:
        from ..logging.base import setup_context as setup_logging_context

        setup_logging_context()

        from .parser import parse_args

        opts, should_run = parse_args()
        debug = getattr(opts, "debug", False)
        profile = getattr(opts, "profile", False)

        from ..utils.pickle import patch_nipype_unpickler

        patch_nipype_unpickler()

        if profile is True:
            from cProfile import Profile

            profiler_instance = Profile()
            profiler_instance.enable()

        from .. import __version__

        logger.info(f"HALFpipe version {__version__}")

        action = getattr(opts, "action", None)
        if action is not None:
            logger.info(f"Running action {action}")
            action(opts)
        else:
            run(opts, should_run)
    except Exception as e:
        logger.exception("Exception: %s", e, exc_info=True)

        if debug:
            import pdb

            pdb.post_mortem()
    finally:
        if profile and profiler_instance is not None:
            profiler_instance.disable()
            if opts is not None:
                from ..utils.time import format_current_time

                profiler_instance.dump_stats(Path(opts.workdir) / f"profile.{format_current_time():s}.prof")

        from ..logging.base import LoggingContext
        from ..logging.base import teardown as teardown_logging

        # ensure queued messages get printed
        LoggingContext.enable_print()

        teardown_logging()

        # clean up orphan processes

        from ..utils.multiprocessing import terminate

        terminate()
