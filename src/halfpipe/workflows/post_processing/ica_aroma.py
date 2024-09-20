# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from math import nan
from pathlib import Path

from fmripost_aroma import config

try:
    from fmripost_aroma.workflows.aroma import init_ica_aroma_wf
except ImportError:
    from fmriprep.workflows.bold.confounds import init_ica_aroma_wf
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe

from ...interfaces.fslnumpy.regfilt import FilterRegressor
from ...interfaces.reports.vals import UpdateVals
from ...interfaces.result.datasink import ResultdictDatasink
from ...interfaces.result.make import MakeResultdicts
from ...interfaces.utility.file_type import SplitByFileType
from ...interfaces.utility.remove_volumes import RemoveVolumes
from ...interfaces.utility.tsv import MergeColumns
from ..memory import MemoryCalculator


def _aroma_column_names(mixing: str | None = None, aroma_noise_ics: str | None = None):
    """
    Generate column names for ICA components, labeling them as either "noise" or "signal"
    based on the input of ICA-AROMA identified noise components.

    Parameters
    ----------
    mixing
        FSL MELODIC mixing matrix
    aroma_noise_ics
        used to be: CSV of noise components identified by ICA-AROMA,
        now this output seems to have disappeared

    Example
    -------
    If there are 10 ICA components in the mixing matrix and components 3 and 7 are identified as noise,
    the function would return:
    >>> column_names, column_indices = _aroma_column_names(mixing_matrix, aroma_noise_ics)
    >>> print(column_names)
    ['aroma_signal_001', 'aroma_signal_002', 'aroma_noise_003',
     'aroma_signal_004', 'aroma_signal_005', 'aroma_signal_006',
     'aroma_noise_007', 'aroma_signal_008', 'aroma_signal_009', 'aroma_signal_010']
    >>> print(column_indices)
    [3, 7]
    """

    from math import ceil, log10

    from halfpipe.utils.matrix import load_vector, ncol

    n_components = ncol(mixing)
    column_indices: list[int] = list(map(int, load_vector(aroma_noise_ics)))

    leading_zeros = int(ceil(log10(n_components)))
    column_names = []
    for i in range(1, n_components + 1):
        if i in column_indices:
            column_names.append(f"aroma_noise_{i:0{leading_zeros}d}")
        else:
            column_names.append(f"aroma_signal_{i:0{leading_zeros}d}")

    return column_names, column_indices


def init_ica_aroma_components_wf(
    workdir: str | None = None,
    name: str = "ica_aroma_components_wf",
    memcalc: MemoryCalculator | None = None,
):
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "alt_bold_std",
                "alt_bold_mask_std",
                "alt_spatial_reference",
                "tags",
                "skip_vols",
                "repetition_time",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(fields=["aroma_noise_ics", "mixing", "features_metadata", "aromavals", "aroma_features"]),
        name="outputnode",
    )

    #
    make_resultdicts = pe.Node(
        MakeResultdicts(reportkeys=["ica_aroma"]),
        name="make_resultdicts",
    )
    workflow.connect(inputnode, "tags", make_resultdicts, "tags")

    #
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(make_resultdicts, "resultdicts", resultdict_datasink, "indicts")

    # Set the dimensionality of the MELODIC ICA decomposition.
    # (default: -200, i.e., estimate <=200 components)
    aroma_melodic_dim = -200
    if config.workflow.melodic_dim is not None:
        aroma_melodic_dim = config.workflow.melodic_dim

    #! There is a new config for fmripost_aroma:
    # config needs to come from fmripost_aroma, not fmriprep
    config.workflow.melodic_dim = aroma_melodic_dim
    config.workflow.denoise_method = None  # disable denoising data
    config.execution.output_dir = Path(workdir) / "derivatives"

    # create ICA-AROMA workflow
    ica_aroma_wf = init_ica_aroma_wf(
        mem_gb={"resampled": memcalc.series_std_gb},
        metadata={"RepetitionTime": nan},
        bold_file="",
    )
    # ? Write unit test for this

    # ? Are these still duplicates
    # remove duplicate nodes
    add_nonsteady = ica_aroma_wf.get_node("add_nonsteady")
    ds_report_ica_aroma = ica_aroma_wf.get_node("ds_report_ica_aroma")
    ica_aroma_wf.remove_nodes([add_nonsteady, ds_report_ica_aroma])

    # connect inputs to ICA-AROMA
    workflow.connect(inputnode, "repetition_time", ica_aroma_wf, "melodic.tr_sec")
    workflow.connect(inputnode, "repetition_time", ica_aroma_wf, "ica_aroma.TR")
    # workflow.connect(inputnode, "movpar_file", ica_aroma_wf, "inputnode.movpar_file")
    workflow.connect(inputnode, "skip_vols", ica_aroma_wf, "inputnode.skip_vols")
    workflow.connect(inputnode, "alt_bold_std", ica_aroma_wf, "inputnode.bold_std")
    workflow.connect(inputnode, "alt_bold_mask_std", ica_aroma_wf, "inputnode.bold_mask_std")
    # workflow.connect(inputnode, "alt_spatial_reference", ica_aroma_wf, "inputnode.spatial_reference")

    # remove dummy scans from outputs
    skip_vols = pe.Node(
        RemoveVolumes(write_header=False),  # melodic_mix files don't have column names
        name="skip_vols",
        mem_gb=memcalc.min_gb,
    )
    workflow.connect(ica_aroma_wf, "outputnode.mixing", skip_vols, "in_file")
    workflow.connect(inputnode, "skip_vols", skip_vols, "skip_vols")

    # pass outputs to outputnode
    workflow.connect(skip_vols, "out_file", outputnode, "mixing")
    workflow.connect(ica_aroma_wf, "outputnode.aroma_features", outputnode, "aroma_features")
    workflow.connect(ica_aroma_wf, "outputnode.features_metadata", outputnode, "features_metadata")
    workflow.connect(ica_aroma_wf, "ica_aroma.aroma_noise_ics", outputnode, "aroma_noise_ics")
    workflow.connect(ica_aroma_wf, "aroma_rpt.out_report", make_resultdicts, "ica_aroma")

    return workflow


def init_ica_aroma_regression_wf(
    workdir: str | None = None,
    name: str = "ica_aroma_regression_wf",
    memcalc: MemoryCalculator | None = None,
    suffix: str | None = None,
):
    """ """
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    if suffix is not None:
        name = f"{name}_{suffix}"
    workflow = pe.Workflow(name=name)

    #
    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "files",
                "mask",
                "tags",
                "vals",
                "mixing",
                "aroma_metadata",
                "aroma_noise_ics",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        niu.IdentityInterface(fields=["files", "mask", "vals"]),
        name="outputnode",
    )

    workflow.connect(inputnode, "mask", outputnode, "mask")

    #
    make_resultdicts = pe.Node(
        MakeResultdicts(),
        name="make_resultdicts",
    )
    workflow.connect(inputnode, "tags", make_resultdicts, "tags")

    #
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(make_resultdicts, "resultdicts", resultdict_datasink, "indicts")

    #
    aroma_column_names = pe.Node(
        interface=niu.Function(
            input_names=["mixing", "aroma_noise_ics"],
            output_names=["column_names", "column_indices"],
            function=_aroma_column_names,
        ),
        name="aroma_column_names",
    )
    workflow.connect(inputnode, "mixing", aroma_column_names, "mixing")
    workflow.connect(inputnode, "aroma_noise_ics", aroma_column_names, "aroma_noise_ics")

    # add mixing to the matrix (used to be melodic_mix)
    split_by_file_type = pe.Node(SplitByFileType(), name="split_by_file_type")
    workflow.connect(inputnode, "files", split_by_file_type, "files")

    merge_columns = pe.Node(MergeColumns(2), name="merge_columns")
    workflow.connect(split_by_file_type, "tsv_files", merge_columns, "in1")
    workflow.connect(inputnode, "mixing", merge_columns, "in2")
    workflow.connect(aroma_column_names, "column_names", merge_columns, "column_names2")

    merge = pe.Node(niu.Merge(2), name="merge")
    workflow.connect(split_by_file_type, "nifti_files", merge, "in1")
    workflow.connect(merge_columns, "out_with_header", merge, "in2")

    #
    filter_regressor = pe.MapNode(
        FilterRegressor(mask=False),
        iterfield="in_file",
        name="filter_regressor",
        mem_gb=memcalc.series_std_gb,
    )

    workflow.connect(merge, "out", filter_regressor, "in_file")
    workflow.connect(inputnode, "mask", filter_regressor, "mask")
    workflow.connect(inputnode, "mixing", filter_regressor, "design_file")
    workflow.connect(aroma_column_names, "column_indices", filter_regressor, "filter_columns")

    workflow.connect(filter_regressor, "out_file", outputnode, "files")

    # We cannot do this in the ica_aroma_components_wf, as having two iterable node
    # with the same name downstream from each other leads nipype to consider them equal
    # even if a joinnode is in between
    # Specifically, both ica_aroma_components_wf and fmriprep's func_preproc_wf use
    # the bold_std_trans_wf that has the iterable node "iterablesource"
    # This way there is no dependency
    aromavals = pe.Node(interface=UpdateVals(), name="aromavals", mem_gb=memcalc.volume_std_gb)
    workflow.connect(inputnode, "vals", aromavals, "vals")
    workflow.connect(inputnode, "aroma_metadata", aromavals, "aroma_metadata")

    workflow.connect(aromavals, "vals", outputnode, "vals")
    workflow.connect(aromavals, "vals", make_resultdicts, "vals")

    return workflow
