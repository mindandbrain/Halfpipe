# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from collections import defaultdict
from typing import Any, Literal, NamedTuple

import nibabel as nib
import numpy as np
import pandas as pd
import scipy
from numba import njit
from numpy import typing as npt

from ..utils.format import format_workflow
from .base import ModelAlgorithm, demean, listwise_deletion
from .miscmaths import f2z_convert, t2z_convert


@njit
def calcgam(
    beta: float,
    y: npt.NDArray[np.float64],
    covariates: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    variance = (s + beta).ravel()
    inverse_variance = np.reciprocal(variance)

    scaled_covariates = covariates.transpose() * inverse_variance
    gram_matrix = np.atleast_2d(scaled_covariates @ covariates)

    regression_weights, _, _, _ = np.linalg.lstsq(gram_matrix, scaled_covariates @ y, rcond=-1.0)

    return regression_weights, inverse_variance, gram_matrix


@njit
def marg_posterior_energy(
    ex: float,
    y: npt.NDArray[np.float64],
    z: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    regression_weights, inverse_variance, gram_matrix = calcgam(ex, y, z, s)
    inverse_variance_logarithmic_determinant = np.log(inverse_variance).sum()
    _, gram_matrix_logarithmic_determinant = np.linalg.slogdet(gram_matrix)
    energy = float(
        -0.5
        * (
            inverse_variance_logarithmic_determinant
            - gram_matrix_logarithmic_determinant
            - ((y.T * inverse_variance) @ y - regression_weights.T @ gram_matrix @ regression_weights).item()
        )
    )

    return energy


def wrapper(
    ex: float,
    y: npt.NDArray[np.float64],
    z: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    if ex < 0 or np.isclose(ex, 0.0):
        return 1e32  # very large value
    try:
        energy = marg_posterior_energy(ex, y, z, s)
        if np.isfinite(energy):
            return energy
    except np.linalg.LinAlgError:
        pass
    return 1e32


def solveforbeta(y: npt.NDArray[np.float64], z: npt.NDArray[np.float64], s: npt.NDArray[np.float64]) -> float:
    result = scipy.optimize.minimize_scalar(wrapper, args=(y, z, s), method="brent")
    beta = max(1e-10, result.x)
    return beta


def flame_stage1_onvoxel(
    y: npt.NDArray[np.float64], z: npt.NDArray[np.float64], s: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    norm = np.std(y)

    if np.isclose(norm, 0):
        raise ValueError("Dependent variable has zero variance")

    y /= norm
    s /= np.square(norm)

    if np.any(s < 0):
        raise ValueError("Variance needs to be non-negative")

    beta = solveforbeta(y, z, s)

    regression_weights, _, gram_matrix = calcgam(beta, y, z, s)

    regression_weights *= norm
    gram_matrix /= np.square(norm)

    return regression_weights, gram_matrix


class TContrastResult(NamedTuple):
    cope: float
    var_cope: float
    t: float
    z: float


def t_ols_contrast(
    regression_weights: npt.NDArray[np.float64],
    gram_matrix: npt.NDArray[np.float64],
    degrees_of_freedom: int,
    t_contrast: npt.NDArray[np.float64],
) -> TContrastResult:
    cope = (t_contrast @ regression_weights).ravel().item()

    a = np.linalg.lstsq(gram_matrix, t_contrast.T, rcond=None)[0]
    var_cope = (t_contrast @ a).ravel().item()

    t = cope / np.sqrt(var_cope)
    z = t2z_convert(t, degrees_of_freedom)

    return TContrastResult(float(cope), float(var_cope), t, z)


class FContrastResult(NamedTuple):
    cope: npt.NDArray[np.float64]
    var_cope: npt.NDArray[np.float64]
    t: npt.NDArray[np.float64]
    f: float
    z: float


def f_ols_contrast(
    regression_weights: npt.NDArray[np.float64],
    gram_matrix: npt.NDArray[np.float64],
    numerator_degrees_of_freedom: int,
    denominator_degrees_of_freedom: int,
    f_contrast: npt.NDArray[np.float64],
):
    cope = (f_contrast @ regression_weights).ravel().astype(np.float64)

    a = f_contrast @ np.linalg.lstsq(gram_matrix, f_contrast.T, rcond=None)[0]
    var_cope = np.diag(a).astype(np.float64)

    t = (cope / np.sqrt(var_cope)).astype(np.float64)
    b = np.linalg.lstsq(a, cope, rcond=None)[0]
    f = float(cope.T @ b) / numerator_degrees_of_freedom
    z = f2z_convert(f, numerator_degrees_of_freedom, denominator_degrees_of_freedom)

    return FContrastResult(cope, var_cope, t, f, z)


def flame1_contrast(mn, inverse_covariance, npts, cmat):
    nevs = len(mn)

    n, _ = cmat.shape

    if n == 1:
        tdoflower = npts - nevs
        t_contrast = t_ols_contrast(mn, inverse_covariance, tdoflower, cmat)
        mask = np.isfinite(t_contrast.z)
        return dict(
            cope=t_contrast.cope,
            var_cope=t_contrast.var_cope,
            dof=tdoflower,
            tstat=t_contrast.t,
            zstat=t_contrast.z,
            mask=mask,
        )

    elif n > 1:
        fdof1 = n

        fdof2lower = npts - nevs

        f_contrast = f_ols_contrast(mn, inverse_covariance, fdof1, fdof2lower, cmat)
        mask = np.isfinite(f_contrast.z)
        return dict(
            cope=f_contrast.cope,
            var_cope=f_contrast.var_cope,
            tstat=f_contrast.t,
            fstat=f_contrast.f,
            dof=[fdof1, fdof2lower],
            zstat=f_contrast.z,
            mask=mask,
        )


def flame1_prepare_data(y: np.ndarray, z: np.ndarray, s: np.ndarray):
    # Filtering for design matrix is already done,
    # so the nans that are left should be replaced with zeros.
    z = np.nan_to_num(z)

    # If we don't have any variance information, set it to zero.
    if np.isnan(s).all():
        s[:] = 0

    # Remove observations with nan cope/varcope
    y, z, s = listwise_deletion(y, z, s)

    # finally demean the design matrix
    z = demean(z)

    return y, z, s


class FLAME1(ModelAlgorithm):
    model_outputs: list[str] = []
    contrast_outputs = [
        "copes",
        "var_copes",
        "zstats",
        "tstats",
        "fstats",
        "dof",
        "masks",
    ]

    @staticmethod
    def voxel_calc(
        coordinate: tuple[int, int, int],
        y: np.ndarray,
        z: np.ndarray,
        s: np.ndarray,
        cmatdict: dict,
    ) -> dict | None:
        y, z, s = flame1_prepare_data(y, z, s)

        npts = y.size

        try:
            mn, inverse_covariance = flame_stage1_onvoxel(y, z, s)
        except (np.linalg.LinAlgError, ValueError, SystemError):
            return None

        voxel_result: dict[str, dict[tuple[int, int, int], Any]] = defaultdict(dict)

        with np.errstate(all="raise"):
            for name, cmat in cmatdict.items():
                try:
                    r = flame1_contrast(mn, inverse_covariance, npts, cmat)
                    voxel_result[name][coordinate] = r
                except (np.linalg.LinAlgError, FloatingPointError, SystemError):
                    continue

        return voxel_result

    @classmethod
    def write_outputs(
        cls,
        reference_image: nib.analyze.AnalyzeImage,
        contrast_matrices: dict,
        voxel_results: dict,
    ) -> dict[str, list[Literal[False] | str]]:
        output_files: dict[str, list[Literal[False] | str]] = dict()

        for output_name in cls.contrast_outputs:
            output_files[output_name] = [False] * len(contrast_matrices)

        for i, contrast_name in enumerate(contrast_matrices.keys()):  # cmatdict is ordered
            contrast_results = voxel_results[contrast_name]
            results_frame = pd.DataFrame.from_records(contrast_results)

            # Ensure that we always output a mask
            if "mask" not in results_frame.index:
                empty_mask = pd.Series(data=False, index=results_frame.columns, name="mask")
                results_frame = results_frame.append(empty_mask)  # type: ignore
            # Ensure that we always output a zstat
            if "zstat" not in results_frame.index:
                empty_zstat = pd.Series(data=np.nan, index=results_frame.columns, name="zstat")
                results_frame = results_frame.append(empty_zstat)  # type: ignore

            for map_name, series in results_frame.iterrows():
                output_prefix = f"{map_name}_{i+1}_{format_workflow(contrast_name)}"
                fname = cls.write_map(reference_image, output_prefix, series)

                if map_name in frozenset(["dof"]):
                    output_name = str(map_name)

                else:
                    output_name = f"{map_name}s"

                if output_name in output_files:
                    output_files[output_name][i] = str(fname)

        return output_files
