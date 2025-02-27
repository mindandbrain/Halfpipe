# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import subprocess

import pytest


def test_fsldir():
    """
    This test verifies:
    1. The 'FSLDIR' environment variable is defined in the system.
    2. The FSL version file exists in the expected location at (?)'FSLDIR/etc/fslversion'.
    This location is maybe not the same anymore. It actually seems to be in /opt/conda/etc/fslconf
    3. The FSL version can be read from the version file and is not empty.
    If any of these conditions fail, the test will raise an assertion error.
    """
    # Check 1) FSLDIR environment variable is set
    fsldir = os.getenv("FSLDIR")
    assert fsldir is not None, "FSLDIR environment variable is not set"

    # Check 2) FSL version file exists
    version_script = "/opt/conda/etc/fslconf/fsl.sh"
    assert os.path.exists(version_script), f"fsl.sh not found at {version_script}"

    # Check 3) Source fsl.sh and get FSL version using 'flirt --version'
    try:
        # Source fsl.sh and run flirt --version in a subprocess
        command = f"source {version_script} && flirt -version"
        result = subprocess.run(
            command, shell=True, executable="/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
        )
        # Capture version from stdout or stderr
        fsl_version = result.stdout.strip() or result.stderr.strip()
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to retrieve FSL version: {e.stderr}")

    # Assert that the version output is not empty
    assert fsl_version, "FSL version output is empty"
    print(f"FSL version: {fsl_version}")
    return fsl_version
