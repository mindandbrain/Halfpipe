# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:


from fmriprep import config
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.utils.spaces import SpatialReferences

from ...interfaces.image_maths.resample import Resample
from ...interfaces.reports.imageplot import PlotEpi, PlotRegistration
from ...interfaces.reports.tsnr import TSNR
from ...interfaces.reports.vals import CalcMean, UpdateVals
from ...interfaces.result.datasink import ResultdictDatasink
from ...interfaces.result.make import MakeResultdicts
from ..constants import Constants
from ..memory import MemoryCalculator


def _calc_scan_start(skip_vols: int, repetition_time: float) -> float:
    return skip_vols * repetition_time


def init_func_report_wf(workdir=None, name="func_report_wf", memcalc: MemoryCalculator | None = None):
    """
    Also creates initial vals

    #TODO: This workflow needs to be split into one calc_start workflow and one report workflow.
    In this way we can comfortably skip the functional report when it is not necessary.

    We need to access the new values of fmriprep for these. This is what they used to be:
    Inputs
    ------
    bold_std
        BOLD series, resampled to template space
    bold_mask_std
        BOLD series mask in template space
    std_dseg: Comes from smriprep
        Segmentation, resampled into standard space
        #TODO: Seems to not exist anymore, so we might want to calculate within this workflow..
    !!!! spatial_reference :obj:`str`
        List of unique identifiers corresponding to the BOLD standard-conversions.
    """

    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    workflow = pe.Workflow(name=name)

    #! need more documentation: why these values and not others? "reg" and "sdc" stopped existing, new exist
    # put all
    fmriprep_reports = ["bold_conf", "bold_rois", "compcor", "conf_corr", "summary", "validation"]
    fmriprep_reportdatasinks = [f"ds_report_{fr}" for fr in fmriprep_reports]

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "boldref",
                # there are two boldref: ds_coreg_boldref_wf & ds_hmc_boldref_wf
                # TODO: Which one we want? Now we use 2nd.
                "boldmask",
                "t1w_dseg",  # used to be std_dseg
                "bold_std",  # bold_std is passed explicitly in fmriprep factory
                # "spatial_reference",   # ! this used to exist in fmriprep!! we dont have a direct substitute
                "output_spaces",
                "movpar_file",
                "confounds_file",
                "method",
                "fallback",
                *fmriprep_reportdatasinks,
                "fd_thres",
                "repetition_time",
                "skip_vols",
                "tags",
            ]
        ),
        name="inputnode",
    )

    # select_std = pe.Node(
    #     # KeySelect(fields=["bold_std", "bold_std_ref", "bold_mask_std", "std_dseg"]),
    #     KeySelect(fields=["bold_std", "boldref", "boldmask", "t1w_dseg"]),
    #     name="select_std",
    #     run_without_submitting=True,
    #     nohash=True,
    # )

    # select_std.inputs.key = f"{Constants.reference_space}_res-{Constants.reference_res}"
    #! next line is a substitute for what used to be "spatial_reference", but we need to re-think this
    # TODO: Either get rid of all select_std nodes, pass output_spaces, use Select interface, or refactor
    #
    # select_std.inputs.keys = [f"{Constants.reference_space}_res-{Constants.reference_res}"]

    # workflow.connect(inputnode, "bold_std", select_std, "bold_std")
    # workflow.connect(inputnode, "boldref", select_std, "boldref")
    # workflow.connect(inputnode, "boldmask", select_std, "boldmask")
    # workflow.connect(inputnode, "t1w_dseg", select_std, "t1w_dseg")

    outputnode = pe.Node(niu.IdentityInterface(fields=["vals"]), name="outputnode")

    #
    make_resultdicts = pe.Node(
        MakeResultdicts(
            imagekeys=["tsnr"],
            reportkeys=["epi_norm_rpt", "tsnr_rpt", "carpetplot", *fmriprep_reports],
            valkeys=[
                "dummy_scans",
                "sdc_method",
                "scan_start",
                "fallback_registration",
            ],
        ),
        name="make_resultdicts",
    )
    workflow.connect(inputnode, "skip_vols", make_resultdicts, "dummy_scans")
    workflow.connect(inputnode, "tags", make_resultdicts, "tags")
    workflow.connect(inputnode, "method", make_resultdicts, "sdc_method")
    workflow.connect(inputnode, "fallback", make_resultdicts, "fallback_registration")

    #
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(make_resultdicts, "resultdicts", resultdict_datasink, "indicts")

    #
    for fr, frd in zip(fmriprep_reports, fmriprep_reportdatasinks, strict=False):
        workflow.connect(inputnode, frd, make_resultdicts, fr)

    # Register EPI to MNI space to use in the QC report
    # EPI -> mni
    spaces = config.workflow.spaces
    assert isinstance(spaces, SpatialReferences)
    epi_norm_rpt = pe.Node(
        PlotRegistration(template=spaces.get_spaces()[0]),
        name="epi_norm_rpt",
        mem_gb=0.1,
    )

    workflow.connect(inputnode, "boldref", epi_norm_rpt, "in_file")
    workflow.connect(inputnode, "boldmask", epi_norm_rpt, "mask_file")
    workflow.connect(epi_norm_rpt, "out_report", make_resultdicts, "epi_norm_rpt")

    # plot the tsnr image
    tsnr = pe.Node(TSNR(), name="compute_tsnr", mem_gb=memcalc.series_std_gb)
    workflow.connect(inputnode, "bold_std", tsnr, "in_file")
    workflow.connect(inputnode, "skip_vols", tsnr, "skip_vols")
    workflow.connect(tsnr, "out_file", make_resultdicts, "tsnr")

    tsnr_rpt = pe.Node(PlotEpi(), name="tsnr_rpt", mem_gb=memcalc.min_gb)
    workflow.connect(tsnr, "out_file", tsnr_rpt, "in_file")
    workflow.connect(inputnode, "boldmask", tsnr_rpt, "mask_file")
    workflow.connect(tsnr_rpt, "out_report", make_resultdicts, "tsnr_rpt")

    #
    reference_dict = dict(reference_space=Constants.reference_space, reference_res=Constants.reference_res)
    reference_dict["input_space"] = reference_dict["reference_space"]
    resample = pe.Node(
        Resample(interpolation="MultiLabel", **reference_dict),
        name="resample",
        #! here we might want to pass the transform anat2std if passing t1w_dseg does not work from the get go
        # Resample(interpolation="MultiLabel", transforms="", **reference_dict),
        mem_gb=2 * memcalc.volume_std_gb,
    )
    workflow.connect(inputnode, "t1w_dseg", resample, "input_image")

    # Calculate the actual starting time and report into the json outputs
    # based on https://github.com/bids-standard/bids-specification/issues/836#issue-954042717
    calc_scan_start = pe.Node(
        niu.Function(
            input_names=["skip_vols", "repetition_time"],
            output_names="scan_start",
            function=_calc_scan_start,
        ),
        name="calc_scan_start",
    )
    workflow.connect(inputnode, "skip_vols", calc_scan_start, "skip_vols")
    workflow.connect(inputnode, "repetition_time", calc_scan_start, "repetition_time")

    workflow.connect(calc_scan_start, "scan_start", make_resultdicts, "scan_start")

    # vals
    confvals = pe.Node(UpdateVals(), name="confvals", mem_gb=2 * memcalc.volume_std_gb)
    workflow.connect(inputnode, "fd_thres", confvals, "fd_thres")
    workflow.connect(inputnode, "confounds_file", confvals, "confounds_file")

    calcmean = pe.Node(
        CalcMean(key="mean_gm_tsnr"),
        name="calcmean",
        mem_gb=2 * memcalc.volume_std_gb,
    )
    workflow.connect(confvals, "vals", calcmean, "vals")  # base dict to update
    workflow.connect(tsnr, "out_file", calcmean, "in_file")
    workflow.connect(resample, "output_image", calcmean, "dseg")

    workflow.connect(calcmean, "vals", make_resultdicts, "vals")
    workflow.connect(make_resultdicts, "vals", outputnode, "vals")

    return workflow
