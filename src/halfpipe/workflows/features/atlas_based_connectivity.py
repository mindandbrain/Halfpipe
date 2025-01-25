# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from pathlib import Path

from nipype.algorithms import confounds as nac
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe

from ...interfaces.connectivity import ConnectivityMeasure
from ...interfaces.image_maths.resample import Resample
from ...interfaces.reports.vals import CalcMean
from ...interfaces.result.datasink import ResultdictDatasink
from ...interfaces.result.make import MakeResultdicts
from ...utils.format import format_workflow
from ..constants import Constants
from ..memory import MemoryCalculator


def init_atlas_based_connectivity_wf(
    workdir: str | Path,
    feature=None,
    atlas_files=None,
    atlas_spaces=None,
    memcalc: MemoryCalculator | None = None,
) -> pe.Workflow:
    """
    Sets up a workflow that is able to perform atlas-based functional connectivity analysis.
    The workflow goes through the following steps by connecting operations in nodes:
    1 Create a resultdict for each atlas (node: `make_resultdicts`)
    2. Use preprocessed bold image to calculate time-course signal-to-noise ratio (SNR) (node: `tsnr`)
    3. Resample atlas files to the reference space and resolution (node: `resample`)
    4. Compute the mean time-course SNR for each resampled atlas (node: `calcmean`)
    5. Calculate the functional connectivity metrics based on the resampled atlas (node: `connectivitymeasure`)
    6. Save the resultdicts to disk (node: `resultdict_datasink`)
    7. Return the resultdicts (node: `outputnode`)

    Parameters
    ----------
    workdir : str or Path
        The working directory where all intermediate and output files will be stored.
    feature : feature object, optional
        A feature object containing the atlases to be used in the analysis, by default None.
    atlas_files : list of Path
        The paths to the atlas files containing the regions of interest for the analysis, by default None.
    atlas_spaces : list of str
        Specific atlas coordinate spaces to be used in the analysis, by default None.
    memcalc : MemoryCalculator, optional
        A memory calculator object for estimating and managing memory usage, by default MemoryCalculator.default().

    Inputs
    ------
    tags : list of str
        Tags for grouping and identifying features in the result dictionary.
    vals : list of str
        Values associated with the tags.
    metadata : dict
        Metadata information related to the input data.
    bold : NIfTI image
        Preprocessed BOLD fMRI image.
    mask : NIfTI image
        Brain mask for the BOLD image.
    repetition_time : float
        Repetition time of the BOLD acquisition.
    atlas_names : list of str
        Names of the atlases used in the analysis.
    atlas_files : list of str or Path
        Paths to the atlas files.
    atlas_spaces : list of str
        Coordinate spaces of the atlases.

    Outputs
    -------
    timeseries : str or Path
        String that points to a path with extracted time-series data (stored in timeseries.tsv)
    covariance_matrix : str or Path
        String that points to a path where the covariance matrix computed
        from the time-series is written (stored in desc-covariance_matrix.tsv)
    correlation_matrix :  str or Path
        String that points to a path where the correlation matrix computed
        from the time-series is written (stored in desc-correlation_matrix.tsv)
    coverage : list of float
        Computed region coverage information (stored in timeseries.json)
    mean_atlas_tsnr : float or list of float
        Mean time-course SNR for each atlas (stored timeseries.json)
    atlas : list of str
        Atlas names used in the analysis
    metadata : dict
        Metadata information related to the input data
    sampling_frequency : float
        Sampling frequency of the BOLD acquisition
    tags : list of str
        Tags for grouping and identifying features in the result dictionary
    vals : list of str
        Values associated with the tags

    Returns
    -------
    workflow : pe.Workflow
        A Nipype Workflow object configured for performing atlas-based functional connectivity analysis.
    """
    memcalc = MemoryCalculator.default() if memcalc is None else memcalc
    if feature is not None:
        name = f"{format_workflow(feature.name)}_wf"
    else:
        name = "atlas_based_connectivity_wf"
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "tags",
                "vals",
                "metadata",
                "bold",
                "mask",
                "repetition_time",
                "atlas_names",
                "atlas_files",
                "atlas_spaces",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(niu.IdentityInterface(fields=["resultdicts"]), name="outputnode")

    min_region_coverage = 0
    if feature is not None:
        inputnode.inputs.atlas_names = feature.atlases
        if hasattr(feature, "min_region_coverage"):
            min_region_coverage = feature.min_region_coverage

    if atlas_files is not None:
        inputnode.inputs.atlas_files = atlas_files

    if atlas_spaces is not None:
        inputnode.inputs.atlas_spaces = atlas_spaces

    #
    make_resultdicts = pe.Node(
        MakeResultdicts(
            tagkeys=["feature", "atlas"],
            imagekeys=["timeseries", "covariance_matrix", "correlation_matrix"],
            metadatakeys=[
                "sources",
                "sampling_frequency",
                "mean_atlas_tsnr",
                "coverage",
            ],
            nobroadcastkeys=["mean_atlas_tsnr", "coverage"],
        ),
        name="make_resultdicts",
    )
    if feature is not None:
        make_resultdicts.inputs.feature = feature.name

    workflow.connect(inputnode, "tags", make_resultdicts, "tags")
    workflow.connect(inputnode, "vals", make_resultdicts, "vals")
    workflow.connect(inputnode, "metadata", make_resultdicts, "metadata")
    workflow.connect(inputnode, "atlas_names", make_resultdicts, "atlas")
    workflow.connect(inputnode, "repetition_time", make_resultdicts, "sampling_frequency")

    workflow.connect(make_resultdicts, "resultdicts", outputnode, "resultdicts")

    #
    resultdict_datasink = pe.Node(ResultdictDatasink(base_directory=workdir), name="resultdict_datasink")
    workflow.connect(make_resultdicts, "resultdicts", resultdict_datasink, "indicts")

    #
    reference_dict = dict(reference_space=Constants.reference_space, reference_res=Constants.reference_res)
    resample = pe.MapNode(
        Resample(interpolation="MultiLabel", **reference_dict),
        name="resample",
        iterfield=["input_image", "input_space"],
        mem_gb=memcalc.series_std_gb,
    )
    workflow.connect(inputnode, "atlas_files", resample, "input_image")
    workflow.connect(inputnode, "atlas_spaces", resample, "input_space")

    #
    connectivitymeasure = pe.MapNode(
        ConnectivityMeasure(background_label=0, min_region_coverage=min_region_coverage),
        name="connectivitymeasure",
        iterfield=["atlas_file"],
        mem_gb=memcalc.series_std_gb,
    )

    workflow.connect(inputnode, "bold", connectivitymeasure, "in_file")
    workflow.connect(inputnode, "mask", connectivitymeasure, "mask_file")
    workflow.connect(resample, "output_image", connectivitymeasure, "atlas_file")

    workflow.connect(connectivitymeasure, "time_series", make_resultdicts, "timeseries")
    workflow.connect(connectivitymeasure, "covariance", make_resultdicts, "covariance_matrix")
    workflow.connect(connectivitymeasure, "correlation", make_resultdicts, "correlation_matrix")
    workflow.connect(connectivitymeasure, "region_coverage", make_resultdicts, "coverage")

    #
    tsnr = pe.Node(interface=nac.TSNR(), name="tsnr", mem_gb=memcalc.series_std_gb)
    workflow.connect(inputnode, "bold", tsnr, "in_file")

    calcmean = pe.MapNode(
        CalcMean(),
        iterfield="parcellation",
        name="calcmean",
        mem_gb=memcalc.series_std_gb,
    )
    workflow.connect(resample, "output_image", calcmean, "parcellation")
    workflow.connect(inputnode, "mask", calcmean, "mask")
    workflow.connect(tsnr, "tsnr_file", calcmean, "in_file")

    workflow.connect(calcmean, "mean", make_resultdicts, "mean_atlas_tsnr")

    return workflow
