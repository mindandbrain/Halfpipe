# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from typing import Final


class Constants:
    reference_space: Final[str] = "MNIPediatricAsym"
    reference_res: Final[int] = 2

    workflow_directory: Final[str] = "nipype"

    grayord_density: Final[str] = "91k"
