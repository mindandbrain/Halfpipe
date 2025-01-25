# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from pathlib import Path
from zipfile import ZipFile

import nibabel as nib
import numpy as np
import pytest
from nilearn.image import new_img_like, resample_to_img

from halfpipe.logging import logger
from halfpipe.resource import get as get_resource
from halfpipe.utils.nipype import run_workflow
from halfpipe.workflows.features.atlas_based_connectivity import (
    init_atlas_based_connectivity_wf,
)

from ...resource import setup as setup_test_resources


@pytest.fixture(scope="module")
def func_file(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp(basename="resources")
    os.chdir(str(tmp_path))
    setup_test_resources()  # updates resource in halfpipe/resource.py with test resources in tests/resource
    bold_file = get_resource(
        "sub-50005_task-rest_bold_space-MNI152NLin2009cAsym_preproc.nii.gz"
    )
    mask_file = tmp_path / "mask.nii.gz"

    image = nib.nifti1.load(bold_file)
    image_data = image.get_fdata()
    mask_data = image_data.std(axis=3) > 0
    mask_image = new_img_like(image, data=mask_data)
    nib.loadsave.save(mask_image, mask_file)

    return [bold_file, mask_file]


@pytest.fixture(scope="module")
def brainnetome_atlas(wd: Path, func_file):
    setup_test_resources()
    atlases_path = get_resource("atlases.zip")
    with ZipFile(atlases_path) as zip_file:
        zip_file.extractall(wd)
    brainnetome_path = wd / "atlas-Brainnetome_dseg.nii.gz"

    # Resample atlas to match the spatial dimensions of the functional image
    func_img = nib.nifti1.load(str(func_file[0]))
    atlas_img = nib.nifti1.load(str(brainnetome_path))
    resampled_atlas = resample_to_img(atlas_img, func_img, interpolation="nearest")
    nib.loadsave.save(resampled_atlas, brainnetome_path)

    return brainnetome_path


@pytest.fixture(scope="session")
def wd(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("test_fc")
    return tmp_path


def test_atlas_fc(wd: Path, func_file, brainnetome_atlas: Path) -> None:
    """
    Checks for node existence and configuration
    Checks that the initialized workflow runs
    Checks the output of the atlas-based connectivity workflow
    Validates correlation and covariance matrices and time series data
    """

    wf = init_atlas_based_connectivity_wf(
        workdir=str(wd),
        atlas_files=brainnetome_atlas,
        atlas_spaces=["MNI152NLin2009cAsym"],
    )

    wf.base_dir = str(wd)
    wf.inputs.inputnode.bold = func_file[0]
    wf.inputs.inputnode.mask = func_file[1]
    wf.inputs.resample.reference_image = brainnetome_atlas

    assert wf.name == "atlas_based_connectivity_wf"
    assert all(
        node_name in [node.name for node in wf._graph.nodes()]
        for node_name in ["inputnode", "make_resultdicts", "calcmean"]
    ), "One or more expected nodes are missing"

    logger.info(f"Brainnetome shape: {nib.nifti1.load(str(brainnetome_atlas)).shape}")
    logger.info(f"Func file shape: {nib.nifti1.load(str(func_file[0])).shape}")
    logger.info(f"Mask file shape: {nib.nifti1.load(str(func_file[1])).shape}")

    flow = run_workflow(wf)

    (resultdicts,) = [n for n in flow.nodes if n.name == "make_resultdicts"]
    out = resultdicts.result.outputs.resultdicts

    logger.info(f"Length of resultdicts: {len(out)}")
    logger.info(
        f"Keys of resultdicts: {out[0].keys()} and {out[1].keys()} and {out[2].keys()}"
    )
    logger.info(f"Resultdicts class: {out.__class__}")

    # Corr matrix checks
    atlas_img = nib.nifti1.load(str(brainnetome_atlas))
    num_regions = (
        len(np.unique(atlas_img.get_fdata())) - 1
    )  # Subtract 1 to exclude background
    correlation_matrix = np.loadtxt(
        wd / "grouplevel" / "func" / "desc-correlation_matrix.tsv", delimiter="\t"
    )
    assert correlation_matrix.shape == (
        num_regions,
        num_regions,
    ), "Correlation matrix shape does not match number of atlas regions"
    assert np.allclose(
        correlation_matrix, correlation_matrix.T, equal_nan=True
    ), "Correlation matrix is not symmetric"
    assert np.allclose(np.diag(correlation_matrix), 1), "Diagonal is not 1"
    assert np.all(
        (-1 <= correlation_matrix) & (correlation_matrix <= 1)
    ), "Correlation matrix values are not between -1 and 1"

    eigenvalues = np.linalg.eigvals(correlation_matrix)
    assert np.all(
        (eigenvalues > 0) | np.isclose(eigenvalues, 0)
    ), "Correlation matrix is not positive-semidefinite"

    # Cov matrix checks
    covariance_matrix = np.loadtxt(
        wd / "grouplevel" / "func" / "desc-covariance_matrix.tsv", delimiter="\t"
    )
    assert covariance_matrix.shape == (
        num_regions,
        num_regions,
    ), "Covariance matrix shape does not match number of atlas regions"
    assert np.allclose(
        covariance_matrix, covariance_matrix.T
    ), "Covariance matrix is not symmetric"

    # Time series check
    ts = np.loadtxt(wd / "grouplevel" / "func" / "timeseries.tsv", delimiter="\t")
    func_shape = nib.nifti1.load(str(func_file[0])).shape
    assert (
        func_shape[3] == ts.shape[0]
    ), "Number of rows in timeseries.tsv does not match number of volumes"
    assert (
        num_regions == ts.shape[1]
    ), "Number of columns in timeseries.tsv does not match number of atlas regions"

    # Validation check with alternative method for calculation of matrices
    np_corr_matrix = np.corrcoef(ts.transpose())
    np_cov_matrix = np.cov(ts.transpose())
    assert np.allclose(
        correlation_matrix, np_corr_matrix
    ), "Output correlation matrix does not match direct calculation"
    assert np.allclose(
        covariance_matrix, np_cov_matrix
    ), "Output covariance matrix does not match direct calculation"
