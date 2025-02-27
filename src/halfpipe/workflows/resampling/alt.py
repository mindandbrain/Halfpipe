# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:


from fmriprep import config
from fmriprep.workflows.bold.apply import init_bold_volumetric_resample_wf
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.utils.spaces import Reference, SpatialReferences
from templateflow.api import get as get_template

from ...resource import get as get_resource
from ..constants import Constants
from ..memory import MemoryCalculator


def init_alt_bold_std_trans_wf(
    name="alt_bold_std_trans_wf",
    spaces: SpatialReferences | None = None,
    memcalc: MemoryCalculator | None = None,
):
    """
    This workflow is needed to run ICA_AROMA.
    This workflow will be ran by default even when ICA_AROMA is not wanted
    because users still want the QC report.

    We do this because we need an extra transform added, which we do in the mergexfm done.
    This extra transform also needs to be applied to the mask at ica_components_wf,
    since the resampled mask used to be outputted by fmriprep but not anymore.

    """
    spaces = SpatialReferences(Reference.from_string("MNI152NLin6Asym:res-2"), checkpoint=True) if spaces is None else spaces
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    workflow = pe.Workflow(name=name)

    # see this
    # https://github.com/nipreps/fmriprep/blob/b6c7b953bb0a07fe466aed556a21ed02ae218da5/fmriprep/workflows/bold/base.py#L460C19-L460C26

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "std_t1w",
                "std_mask",
                "bold_minimal",
                "coreg_boldref",  # comes from bold_fit_wf.outputnode.coreg_boldref',
                # "bold_ref_file",
                # "bold_mask",
                "boldref2anat_xfm",
                "out_warp",
                "anat2std_xfm",
                "motion_xfm",
                # "bold_native_wf.outputnode.motion_xfm", #we want motion_xfm from bold_native_wf, not from bold_fit_wf
            ]
        ),
        name="inputnode",
    )

    bold_std_trans_wf_outputs = ["bold_file", "resampling_reference"]
    outputnode = pe.Node(
        niu.IdentityInterface(fields=[f"alt_{a}" for a in bold_std_trans_wf_outputs]),
        name="outputnode",
    )

    #
    alt_reference_spaces = spaces.get_spaces(nonstandard=False, dim=(3,))

    # We use ravel_inputs to flatten the list, to have just a list instead of a list of lists
    mergexfm = pe.MapNode(niu.Merge(numinputs=2, ravel_inputs=True), iterfield="in1", name="mergexfm")  # no_flatten = false?
    mergexfm.inputs.in1 = [
        get_resource(f"tpl_{alt}_from_{Constants.reference_space}_mode_image_xfm.h5") for alt in alt_reference_spaces
    ]
    workflow.connect(inputnode, "anat2std_xfm", mergexfm, "in2")  # in the fmriprep resample one this one is not there

    bold_std_trans_wf = init_bold_volumetric_resample_wf(
        metadata={},  # We pass empty metadata so we can reuse workflow between subjects
        jacobian=True,  # TODO: True or false? no documentation in FMRIPREP https://github.com/nipreps/fmriprep/blob/master/fmriprep/workflows/bold/apply.py#L19
        mem_gb={"resampled": memcalc.volume_std_gb},  # was memcalc.volume_std_gb
        omp_nthreads=config.nipype.omp_nthreads,
        name="bold_volumetric_resample_trans_wf",
    )

    bold_std_trans_wf_inputnode = bold_std_trans_wf.get_node("inputnode")
    assert isinstance(bold_std_trans_wf_inputnode, pe.Node)

    # Derive target reference file
    target_ref_file = get_template("MNI152NLin6Asym", resolution=2, desc="brain", suffix="T1w")
    bold_std_trans_wf_inputnode.inputs.target_ref_file = target_ref_file  # fixed_image

    fmriprep_merge_node = bold_std_trans_wf.get_node("boldref2target")
    fmriprep_merge_node.inputs.ravel_inputs = True
    fmriprep_merge_node.inputs.no_flatten = False

    workflow.connect(mergexfm, "out", bold_std_trans_wf, "inputnode.anat2std_xfm")
    # workflow.connect(inputnode, "std_t1w", bold_std_trans_wf, "inputnode.target_ref_file")    # same
    workflow.connect(inputnode, "bold_minimal", bold_std_trans_wf, "inputnode.bold_file")
    workflow.connect(inputnode, "coreg_boldref", bold_std_trans_wf, "inputnode.bold_ref_file")  # moving_image
    workflow.connect(inputnode, "motion_xfm", bold_std_trans_wf, "inputnode.motion_xfm")  # its a text file instead of h5
    workflow.connect(inputnode, "boldref2anat_xfm", bold_std_trans_wf, "inputnode.boldref2anat_xfm")
    workflow.connect(inputnode, "std_mask", bold_std_trans_wf, "inputnode.target_mask")

    for a in bold_std_trans_wf_outputs:
        workflow.connect(bold_std_trans_wf, f"outputnode.{a}", outputnode, f"alt_{a}")

    return workflow
