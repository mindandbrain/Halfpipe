# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from pathlib import Path

import nipype.interfaces.utility as niu
import nipype.pipeline.engine as pe
from nipype.interfaces import afni

from ...interfaces.image_maths.lazy_blur import LazyBlurToFWHM
from ...interfaces.image_maths.zscore import ZScore
from ...interfaces.result.datasink import ResultdictDatasink
from ...interfaces.result.make import MakeResultdicts
from ...utils.format import format_workflow
from ..memory import MemoryCalculator


def compute_falff(mask_file, filtered_file, unfiltered_file):
    """
    Computes fALFF using Nibabel instead of AFNI's 3dcalc.
    """
    import os

    import nibabel as nib

    mask_img = nib.load(mask_file)
    filtered_img = nib.load(filtered_file)
    unfiltered_img = nib.load(unfiltered_file)

    mask_data = mask_img.get_fdata()
    filtered_data = filtered_img.get_fdata()
    unfiltered_data = unfiltered_img.get_fdata()

    falff_data = (mask_data > 0) * (filtered_data / (unfiltered_data + 1e-6))
    falff_img = nib.Nifti1Image(falff_data, affine=mask_img.affine, header=mask_img.header)

    # Save file with absolute path
    output_file = os.path.abspath("falff_output.nii.gz")
    nib.save(falff_img, output_file)

    return output_file


def init_falff_wf(
    workdir: str | Path,
    feature=None,
    fwhm=None,
    memcalc: MemoryCalculator | None = None,
) -> pe.Workflow:
    """
    Calculate Amplitude of low frequency oscillations(ALFF) and
    fractional ALFF maps

    Returns
    -------
    workflow : workflow object
        ALFF workflow

    Notes
    -----
    Adapted from
    <https://github.com/FCP-INDI/C-PAC/blob/master/CPAC/alff/alff.py>

    """
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    if feature is not None:
        name = f"{format_workflow(feature.name)}"
    else:
        name = "falff"
    if fwhm is not None:
        name = f"{name}_{int(float(fwhm) * 1e3):d}"
    name = f"{name}_wf"
    workflow = pe.Workflow(name=name)

    # input
    inputnode = pe.Node(
        niu.IdentityInterface(fields=["tags", "vals", "metadata", "bold", "mask", "fwhm"]),
        name="inputnode",
    )
    unfiltered_inputnode = pe.Node(
        niu.IdentityInterface(fields=["bold", "mask"]),
        name="unfiltered_inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=["resultdicts"]), name="outputnode")

    if fwhm is not None:
        inputnode.inputs.fwhm = float(fwhm)
    elif feature is not None and hasattr(feature, "smoothing"):
        inputnode.inputs.fwhm = feature.smoothing.get("fwhm")

    #
    make_resultdicts = pe.Node(
        MakeResultdicts(tagkeys=["feature"], imagekeys=["alff", "falff", "mask"]),
        name="make_resultdicts",
    )
    if feature is not None:
        make_resultdicts.inputs.feature = feature.name
    workflow.connect(inputnode, "tags", make_resultdicts, "tags")
    workflow.connect(inputnode, "vals", make_resultdicts, "vals")
    workflow.connect(inputnode, "metadata", make_resultdicts, "metadata")
    workflow.connect(inputnode, "mask", make_resultdicts, "mask")

    workflow.connect(make_resultdicts, "resultdicts", outputnode, "resultdicts")

    #
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(make_resultdicts, "resultdicts", resultdict_datasink, "indicts")

    # standard deviation of the filtered image
    stddev_filtered = pe.Node(afni.TStat(), name="stddev_filtered", mem_gb=memcalc.series_std_gb)
    stddev_filtered.inputs.outputtype = "NIFTI_GZ"
    stddev_filtered.inputs.options = "-stdev"
    workflow.connect(inputnode, "bold", stddev_filtered, "in_file")
    workflow.connect(inputnode, "mask", stddev_filtered, "mask")

    # standard deviation of the unfiltered image
    stddev_unfiltered = pe.Node(afni.TStat(), name="stddev_unfiltered", mem_gb=memcalc.series_std_gb)
    stddev_unfiltered.inputs.outputtype = "NIFTI_GZ"
    stddev_unfiltered.inputs.options = "-stdev"
    workflow.connect(unfiltered_inputnode, "bold", stddev_unfiltered, "in_file")
    workflow.connect(unfiltered_inputnode, "mask", stddev_unfiltered, "mask")

    # calculate falff
    falff = pe.Node(
        niu.Function(
            input_names=["mask_file", "filtered_file", "unfiltered_file"],
            output_names=["out_file"],
            function=compute_falff,
        ),
        name="falff",
    )

    workflow.connect(inputnode, "mask", falff, "mask_file")
    workflow.connect(stddev_filtered, "out_file", falff, "filtered_file")
    workflow.connect(stddev_unfiltered, "out_file", falff, "unfiltered_file")

    #
    merge = pe.Node(niu.Merge(2), name="merge")
    workflow.connect(stddev_filtered, "out_file", merge, "in1")
    workflow.connect(falff, "out_file", merge, "in2")

    smooth = pe.MapNode(LazyBlurToFWHM(outputtype="NIFTI_GZ"), iterfield="in_file", name="smooth")
    workflow.connect(merge, "out", smooth, "in_file")
    workflow.connect(inputnode, "mask", smooth, "mask")
    workflow.connect(inputnode, "fwhm", smooth, "fwhm")

    zscore = pe.MapNode(ZScore(), iterfield="in_file", name="zscore", mem_gb=memcalc.volume_std_gb)
    workflow.connect(smooth, "out_file", zscore, "in_file")
    workflow.connect(inputnode, "mask", zscore, "mask")

    split = pe.Node(niu.Split(splits=[1, 1]), name="split")
    workflow.connect(zscore, "out_file", split, "inlist")

    workflow.connect(split, "out1", make_resultdicts, "alff")
    workflow.connect(split, "out2", make_resultdicts, "falff")

    return workflow
