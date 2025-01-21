# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from typing import NamedTuple

import nibabel as nib
import numpy as np
import pandas as pd
import scipy
from numpy import typing as npt

from ..logging import logger
from .base import ModelAlgorithm
from .flame1 import flame1_prepare_data


def method_of_moments_i_squared(
    y: npt.NDArray[np.float64],
    z: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    """
    Chen et al. 2012
    """

    b = y
    x = z
    w0 = np.diag(1.0 / s.ravel())

    n, p = x.shape

    w0x = w0 @ x
    hat = np.linalg.lstsq(x.T @ w0x, w0x.T, rcond=-1.0)[0]
    a0 = hat @ b

    r = b - x @ a0
    q = r.T @ w0 @ r

    p0 = w0 - w0x @ hat

    trp0 = np.trace(p0)

    τ2 = ((q - (n - p - 1)) / trp0).item()
    if τ2 < 0:
        τ2 = 0

    h2 = τ2 * trp0 / (n - p - 1) + 1
    i2 = (h2 - 1) / h2

    return i2


class ReMLTerms(NamedTuple):
    inverse_variance: npt.NDArray[np.float64]
    projection_matrix: npt.NDArray[np.float64]
    gram_matrix: npt.NDArray[np.float64]


def reml_terms(ϑ: float, x: npt.NDArray[np.float64], s: npt.NDArray[np.float64]) -> ReMLTerms:
    inverse_variance = np.reciprocal(1.0 / (s + ϑ)).ravel()

    a = x.T * inverse_variance
    gram_matrix = a @ x

    # projection matrix
    projection_matrix = np.diag(inverse_variance) - a.T @ np.linalg.lstsq(gram_matrix, a, rcond=-1.0)[0]
    return ReMLTerms(inverse_variance, projection_matrix, gram_matrix)


def reml_neg_log_lik(
    ϑ: float,
    y: npt.NDArray[np.float64],
    x: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    if np.isclose(ϑ, 0) or ϑ < 0:
        return np.inf
    terms = reml_terms(ϑ, x, s)

    logarithmic_determinant = np.log(terms.inverse_variance).sum()
    neg_log_lik = -0.5 * logarithmic_determinant

    _, log_det_xvinvx = np.linalg.slogdet(terms.gram_matrix)
    neg_log_lik += 0.5 * log_det_xvinvx
    neg_log_lik += 0.5 * (y.T @ terms.projection_matrix @ y).item()

    return neg_log_lik.item()


def reml_fit(
    y: npt.NDArray[np.float64],
    x: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> scipy.optimize.OptimizeResult:
    return scipy.optimize.minimize_scalar(reml_neg_log_lik, args=(y, x, s), method="brent")


def reml_jacobian(
    ϑ: float,
    y: npt.NDArray[np.float64],
    x: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    terms = reml_terms(ϑ, x, s)
    p = terms.projection_matrix
    return float(np.trace(p) - y.T @ p @ p @ y)


def reml_hessian(
    ϑ: float,
    y: npt.NDArray[np.float64],
    x: npt.NDArray[np.float64],
    s: npt.NDArray[np.float64],
) -> float:
    terms = reml_terms(ϑ, x, s)
    p = terms.projection_matrix
    return (y.T @ p @ p @ p @ y).item()


def ml_neg_log_lik(
    ϑ: float,
    y: npt.NDArray[np.floating],
    x: npt.NDArray[np.floating] | None,
    s: npt.NDArray[np.floating],
    γ: npt.NDArray[np.floating],
):
    if ϑ < 0:
        return np.inf
    vinv = np.diag(np.ravel(1.0 / (s + ϑ)))

    n = y.size
    neg_log_lik = n * np.log(2 * np.pi) / 2

    _, log_det_vinv = np.linalg.slogdet(vinv)
    neg_log_lik += -log_det_vinv.item() / 2

    if x is None:
        return neg_log_lik

    r: npt.NDArray[np.float64] = (y - x @ γ).astype(np.float64)
    neg_log_lik += float(r.T @ vinv @ r) / 2

    return neg_log_lik


def inv_gamma_ml_fit(x: npt.NDArray[np.float64]):
    a, _, scale = scipy.stats.invgamma.fit(x, floc=0)
    ϑ = np.array([a, scale])
    return ϑ


def inv_gamma_ml_neg_log_lik(ϑ: npt.NDArray[np.float64], x: npt.NDArray[np.float64]):
    a, b = ϑ

    if a < 0 or b < 0:
        return np.inf

    n = x.size

    u = np.sum(np.log(x))
    v = np.sum(1 / x)

    return -n * a * np.log(b) + n * np.log(scipy.special.gamma(a)) + a * u + u + b * v


def inv_gamma_ml_jacobian(ϑ: npt.NDArray[np.float64], x: npt.NDArray[np.float64]):
    a, b = ϑ

    if a < 0 or b < 0:
        return np.array([np.nan] * 2)

    n = x.size

    u = np.sum(np.log(x))
    v = np.sum(1 / x)

    return np.array(
        [
            -n * np.log(b) + n * scipy.special.digamma(a) + u,
            -n * a / b + v,
        ]
    )


def inv_gamma_ml_hessian(ϑ: npt.NDArray[np.float64], x: npt.NDArray[np.float64]):
    a, b = ϑ

    if a < 0 or b < 0:
        return np.array([[np.nan] * 2] * 2)

    n = x.size

    return n * np.array(
        [
            [scipy.special.polygamma(1, a), -1 / b],
            [-1 / b, a / np.square(b)],
        ]
    )


def het_on_voxel(y, z, s):
    assert not np.any(s < 0), "Variance needs to be non-negative"

    # Scale to avoid numerical issues
    norm = np.std(y)
    y_norm = y / norm
    s_norm = s / (norm * norm)

    # Calculate beta
    neg_log_lik_fe = reml_neg_log_lik(0, y_norm, z, s_norm)

    res = reml_fit(y_norm, z, s_norm)
    neg_log_lik_me = res.fun

    var_res = 1 / reml_hessian(res.x, y_norm, z, s_norm)
    beta = np.array([res.x, var_res])
    beta *= norm * norm

    # Calculate likelihood ratio test
    chisq = 2 * (neg_log_lik_fe - neg_log_lik_me)

    with np.errstate(divide="ignore", invalid="ignore"):
        pseudor2 = 1 - neg_log_lik_me / neg_log_lik_fe
    if np.isfinite(pseudor2):
        pseudor2 = max(0, min(1, pseudor2))

    # Calculate other statistics
    i_squared = method_of_moments_i_squared(y_norm, z, s_norm)

    ϑ = inv_gamma_ml_fit(s)
    var_ϑ = np.linalg.inv(inv_gamma_ml_hessian(ϑ, s))
    gamma = np.vstack([ϑ, var_ϑ])

    n = s.size
    u = np.sum(1 / s)
    v = np.sum(1 / np.square(s))
    νq = (n - 1) * u / (np.square(u) - v)
    typical = float(νq)

    return dict(
        hetnorm=norm,
        hetbeta=beta,
        hetgamma=gamma,
        hettypical=typical,
        heti2=i_squared,
        hetpseudor2=pseudor2,
        hetchisq=chisq,
    )


class Heterogeneity(ModelAlgorithm):
    model_outputs: list[str] = [
        "hetnorm",
        "hetbeta",
        "hetgamma",
        "hettypical",
        "heti2",
        "hetpseudor2",
        "hetchisq",
    ]
    contrast_outputs: list[str] = []

    @staticmethod
    def voxel_calc(
        coordinate: tuple[int, int, int],
        y: npt.NDArray[np.float64],
        z: npt.NDArray[np.float64],
        s: npt.NDArray[np.float64],
        cmatdict: dict,
    ) -> dict | None:
        _ = cmatdict
        y, z, s = flame1_prepare_data(y, z, s)

        try:
            voxel_dict = het_on_voxel(y, z, s)
        except (np.linalg.LinAlgError, SystemError):
            return None
        except Exception as e:
            logger.warning(f"Unexpected exception for voxel {coordinate}", exc_info=e)
            return None

        if voxel_dict is None:
            return None

        voxel_result = {coordinate: voxel_dict}
        return voxel_result

    @classmethod
    def write_outputs(cls, ref_img: nib.analyze.AnalyzeImage, cmatdict: dict, voxel_results: dict) -> dict:
        output_files = dict()

        rdf = pd.DataFrame.from_records(voxel_results)

        for map_name, series in rdf.iterrows():
            assert isinstance(map_name, str)

            fname = cls.write_map(ref_img, map_name, series)
            output_files[map_name] = str(fname)

        return output_files
