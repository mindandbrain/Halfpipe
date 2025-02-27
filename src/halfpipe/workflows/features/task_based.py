# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from math import isfinite
from pathlib import Path

import nipype.algorithms.modelgen as model
import numpy as np
from nipype.interfaces import fsl
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe

from ...interfaces.conditions import ApplyConditionOffset, ParseConditionFile
from ...interfaces.fixes.level1design import Level1Design
from ...interfaces.result.datasink import ResultdictDatasink
from ...interfaces.result.make import MakeResultdicts
from ...interfaces.stats.dof import MakeDofVolume
from ...interfaces.utility.tsv import FillNA, MergeColumns
from ...interfaces.utility.vest import Unvest
from ...utils.format import format_workflow
from ...utils.ops import first_float, first_str, ravel
from ..memory import MemoryCalculator


def _add_td_conditions(hrf, condition_names):
    if hrf == "dgamma":
        return condition_names

    elif hrf == "dgamma_with_derivs":
        suffixes = ["", "TD"]

    elif hrf == "flobs":
        suffixes = ["", "FN2", "FN3"]  #

    else:
        raise ValueError(f'Unknown HRF "{hrf}"')

    return [f"{c}{suffix}" for c in condition_names for suffix in suffixes]


def _get_scan_start(vals) -> float:
    scan_start = vals["scan_start"]
    assert isinstance(scan_start, float)
    return scan_start


def init_taskbased_wf(
    workdir: Path | str,
    feature,
    condition_files: tuple[str | tuple[str, str], ...],
    condition_units,
    memcalc: MemoryCalculator | None = None,
):
    """
    create workflow to calculate a first level glm for task functional data
    """
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    if feature is not None:
        name = f"{format_workflow(feature.name)}_wf"
    else:
        name = "taskbased_wf"
    workflow = pe.Workflow(name=name)

    #
    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "tags",
                "vals",
                "metadata",
                "bold",
                "mask",
                "repetition_time",
                "confounds_selected",
                "condition_names",
                "condition_files",
                "condition_units",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=["resultdicts"]), name="outputnode")

    inputnode.inputs.condition_names = feature.conditions

    if condition_files is not None:
        inputnode.inputs.condition_files = condition_files

    if condition_units is not None:
        inputnode.inputs.condition_units = condition_units

    #
    make_resultdicts_a = pe.Node(
        MakeResultdicts(tagkeys=["feature"], imagekeys=["design_matrix", "contrast_matrix"]),
        name="make_resultdicts_a",
    )
    if feature is not None:
        make_resultdicts_a.inputs.feature = feature.name
    workflow.connect(inputnode, "tags", make_resultdicts_a, "tags")
    workflow.connect(inputnode, "vals", make_resultdicts_a, "vals")
    workflow.connect(inputnode, "metadata", make_resultdicts_a, "metadata")
    make_resultdicts_b = pe.Node(
        MakeResultdicts(
            tagkeys=["feature", "taskcontrast"],
            imagekeys=["effect", "variance", "sigmasquareds", "z", "dof", "mask"],
            metadatakeys=["sources"],
        ),
        name="make_resultdicts_b",
    )
    if feature is not None:
        make_resultdicts_b.inputs.feature = feature.name
    workflow.connect(inputnode, "tags", make_resultdicts_b, "tags")
    workflow.connect(inputnode, "vals", make_resultdicts_b, "vals")
    workflow.connect(inputnode, "metadata", make_resultdicts_b, "metadata")
    workflow.connect(inputnode, "mask", make_resultdicts_b, "mask")

    workflow.connect(make_resultdicts_b, "resultdicts", outputnode, "resultdicts")

    #
    merge_resultdicts = pe.Node(niu.Merge(2), name="merge_resultdicts")
    workflow.connect(make_resultdicts_a, "resultdicts", merge_resultdicts, "in1")
    workflow.connect(make_resultdicts_b, "resultdicts", merge_resultdicts, "in2")
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(merge_resultdicts, "out", resultdict_datasink, "indicts")

    # transform contrasts dictionary to nipype list data structure
    contrasts = []
    condition_names = feature.conditions
    for contrast in feature.contrasts:
        contrast_values = [contrast["values"].get(c, 0.0) for c in condition_names]
        contrasts.append(
            [
                contrast["name"],
                contrast["type"].upper(),
                condition_names,
                contrast_values,
            ]
        )

    # parse condition files into three (ordered) lists
    parse_condition_file = pe.Node(ParseConditionFile(contrasts=contrasts), name="parse_condition_file")
    workflow.connect(inputnode, "condition_names", parse_condition_file, "condition_names")
    workflow.connect(inputnode, "condition_files", parse_condition_file, "in_any")
    workflow.connect(parse_condition_file, "contrast_names", make_resultdicts_b, "taskcontrast")

    #
    get_scan_start = pe.Node(
        niu.Function(
            input_names=["vals"],
            output_names=["scan_start"],
            function=_get_scan_start,
        ),
        name="get_scan_start",
    )
    workflow.connect(inputnode, "vals", get_scan_start, "vals")

    apply_condition_offset = pe.Node(ApplyConditionOffset(), name="apply_condition_offset")
    workflow.connect(parse_condition_file, "subject_info", apply_condition_offset, "subject_info")
    workflow.connect(get_scan_start, "scan_start", apply_condition_offset, "scan_start")

    #
    fillna = pe.Node(FillNA(), name="fillna")
    workflow.connect(inputnode, "confounds_selected", fillna, "in_tsv")

    # first level model specification
    modelspec = pe.Node(model.SpecifyModel(), name="modelspec")

    modelspec.inputs.high_pass_filter_cutoff = np.inf  # disable if missing
    if hasattr(feature, "high_pass_filter_cutoff"):
        hpfc = feature.high_pass_filter_cutoff
        if isinstance(hpfc, float) and isfinite(hpfc):
            modelspec.inputs.high_pass_filter_cutoff = hpfc

    workflow.connect(inputnode, "bold", modelspec, "functional_runs")
    workflow.connect(inputnode, "condition_units", modelspec, "input_units")
    workflow.connect(inputnode, "repetition_time", modelspec, "time_repetition")
    workflow.connect(fillna, "out_no_header", modelspec, "realignment_parameters")
    workflow.connect(apply_condition_offset, "subject_info", modelspec, "subject_info")

    # generate design from first level specification
    if feature.hrf == "dgamma":
        bases: dict[str, dict] = dict(dgamma=dict())
    elif feature.hrf == "dgamma_with_derivs":
        bases = dict(dgamma=dict(derivs=True))
    elif feature.hrf == "flobs":
        bfcustompath = Path(os.environ["FSLDIR"]) / "etc" / "default_flobs.flobs" / "hrfbasisfns.txt"
        assert bfcustompath.is_file()
        bases = dict(
            custom=dict(
                bfcustompath=str(bfcustompath),
                basisfnum=3,
            )
        )
    else:
        raise ValueError(f'HRF "{feature.hrf}" is not yet implemented')

    level1design = pe.Node(
        Level1Design(
            model_serial_correlations=True,
            bases=bases,
        ),
        name="level1design",
    )
    workflow.connect(parse_condition_file, "contrasts", level1design, "contrasts")
    workflow.connect(inputnode, "repetition_time", level1design, "interscan_interval")
    workflow.connect(modelspec, "session_info", level1design, "session_info")

    # generate required input files for FILMGLS from design
    modelgen = pe.Node(fsl.FEATModel(), name="modelgen", mem_gb=1.0)
    workflow.connect([(level1design, modelgen, [(("fsf_files", first_str), "fsf_file")])])
    workflow.connect([(level1design, modelgen, [(("ev_files", ravel), "ev_files")])])

    # calculate range of image values to determine cutoff value
    stats = pe.Node(
        fsl.ImageStats(op_string="-R"),
        name="stats",
        mem_gb=memcalc.series_std_gb,
    )
    workflow.connect(inputnode, "bold", stats, "in_file")
    cutoff = pe.Node(
        niu.Function(input_names=["obj"], output_names=["min_val"], function=first_float),
        name="cutoff",
    )
    workflow.connect(stats, "out_stat", cutoff, "obj")

    # fslversion = fsl.Info.version()
    # pdb.set_trace()

    # actually estimate the first level model
    # ? tconf_file is not taken anymore by nipype interface?
    modelestimate = pe.Node(
        fsl.FILMGLS(smooth_autocorr=True, mask_size=5),
        name="modelestimate",
        mem_gb=memcalc.series_std_gb * 1.5,
    )

    # FILMGLS is not detecting the right version of FSL

    # FSL DIR needs to be set: fmriprep 20 dockerfile
    workflow.connect(inputnode, "bold", modelestimate, "in_file")
    workflow.connect(cutoff, "min_val", modelestimate, "threshold")
    workflow.connect(modelgen, "design_file", modelestimate, "design_file")
    workflow.connect(modelgen, "con_file", modelestimate, "tcon_file")
    workflow.connect(modelgen, "fcon_file", modelestimate, "fcon_file")

    # make dof volume
    makedofvolume = pe.Node(MakeDofVolume(), iterfield=["dof_file", "copes"], name="makedofvolume")
    workflow.connect(modelestimate, "copes", makedofvolume, "copes")
    workflow.connect(modelestimate, "dof_file", makedofvolume, "dof_file")

    workflow.connect(modelestimate, "copes", make_resultdicts_b, "effect")
    workflow.connect(modelestimate, "varcopes", make_resultdicts_b, "variance")
    workflow.connect(modelestimate, "sigmasquareds", make_resultdicts_b, "sigmasquareds")
    workflow.connect(modelestimate, "zstats", make_resultdicts_b, "z")
    workflow.connect(makedofvolume, "out_file", make_resultdicts_b, "dof")

    #
    mergecolumnnames = pe.Node(niu.Merge(2), name="mergecolumnnames")
    workflow.connect(fillna, "column_names", mergecolumnnames, "in2")

    if feature.hrf != "dgamma":
        add_td_conditions = pe.Node(
            niu.Function(
                input_names=["hrf", "condition_names"],
                output_names=["condition_names"],
                function=_add_td_conditions,
            ),
            name="add_td_conditions",
        )
        add_td_conditions.inputs.hrf = feature.hrf
        workflow.connect(
            parse_condition_file,
            "condition_names",
            add_td_conditions,
            "condition_names",
        )

        workflow.connect(add_td_conditions, "condition_names", mergecolumnnames, "in1")
    else:
        workflow.connect(parse_condition_file, "condition_names", mergecolumnnames, "in1")

    #
    design_unvest = pe.Node(Unvest(), name="design_unvest")
    workflow.connect(modelgen, "design_file", design_unvest, "in_vest")

    design_tsv = pe.Node(MergeColumns(1), name="design_tsv")
    workflow.connect(design_unvest, "out_no_header", design_tsv, "in1")
    workflow.connect(mergecolumnnames, "out", design_tsv, "column_names1")

    contrast_unvest = pe.Node(Unvest(), name="contrast_unvest")
    workflow.connect(modelgen, "con_file", contrast_unvest, "in_vest")

    contrast_tsv = pe.Node(MergeColumns(1), name="contrast_tsv")
    workflow.connect(parse_condition_file, "contrast_names", contrast_tsv, "row_index")
    workflow.connect(contrast_unvest, "out_no_header", contrast_tsv, "in1")
    workflow.connect(mergecolumnnames, "out", contrast_tsv, "column_names1")

    workflow.connect(design_tsv, "out_with_header", make_resultdicts_a, "design_matrix")
    workflow.connect(contrast_tsv, "out_with_header", make_resultdicts_a, "contrast_matrix")

    return workflow
