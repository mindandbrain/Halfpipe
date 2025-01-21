# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import re
from typing import Dict, Optional, Tuple

import nibabel as nib
import numpy as np
import pint

from ...logging import logger
from ...utils.path import split_ext

ureg = pint.UnitRegistry()

descrip_pattern = re.compile(r"(?P<var_name>\w+)=(?P<value>(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)(?P<unit>s|ms|us)?")


def parse_descrip(header: nib.nifti1.Nifti1Header) -> dict[str, float]:
    descrip_dict = dict()

    descrip_array = header.get("descrip")
    assert isinstance(descrip_array, np.ndarray)
    descrip = descrip_array.tolist()

    # mypy complain, thus:
    if isinstance(descrip, bytes):
        descrip = descrip.decode()

    for m in descrip_pattern.finditer(descrip):
        var_name = m.group("var_name")
        value = m.group("value")
        unit = m.group("unit")

        assert isinstance(var_name, str)

        var_name = var_name.lower()
        value = float(value)

        key = None

        if var_name == "te":
            if unit is None:
                if value < 1:  # heuristic
                    unit = "s"
                else:
                    unit = "ms"

            key = "echo_time"

        elif var_name == "tr":
            if unit is None:
                if value > 100:  # heuristic
                    unit = "ms"
                else:
                    unit = "s"

            key = "repetition_time"

        if key is not None:
            base_quantity = ureg(unit)
            assert isinstance(base_quantity, pint.Quantity)

            quantity = value * base_quantity

            descrip_dict[key] = quantity.m_as(ureg.seconds)

    return descrip_dict


class NiftiheaderLoader:
    cache: dict[str, tuple[nib.nifti1.Nifti1Header, dict[str, float]]] = dict()

    @classmethod
    def load(cls, nifti_file: str) -> Tuple[Optional[nib.nifti1.Nifti1Header], Optional[Dict]]:
        if nifti_file in cls.cache:
            return cls.cache[nifti_file]

        _, ext = split_ext(nifti_file)

        if ext in [".mat", ".json"]:  # don't even try for these extensions
            return None, None

        try:
            img = nib.nifti1.load(nifti_file)
        except Exception as e:
            logger.warning(f'Caught error loading file "{nifti_file}": %s', e, exc_info=True)
            return None, None

        header = img.header.copy()

        try:
            descrip_dict = parse_descrip(header)
        except Exception as e:
            logger.info(
                f'Could not parse nii file descrip for "{nifti_file:s}: %s"',
                e,
                exc_info=True,
            )
            descrip_dict = dict()

        cls.cache[nifti_file] = header, descrip_dict
        return header, descrip_dict
