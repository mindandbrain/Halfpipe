# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import tarfile

import pytest

from halfpipe.resource import get as get_resource

from .resource import setup as setup_test_resources

os.environ["FSLOUTPUTTYPE"] = "NIFTI_GZ"


@pytest.fixture(scope="session")
def wakemandg_hensonrn_raw(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp(basename="wakemandg_hensonrn")

    os.chdir(str(tmp_path))

    setup_test_resources()
    inputtarpath = get_resource("wakemandg_hensonrn_statmaps.tar.gz")

    with tarfile.open(inputtarpath) as fp:
        fp.extractall(tmp_path)

    subjects = [f"{i + 1:02d}" for i in range(16)]
    suffixes = ["stat-effect_statmap", "stat-variance_statmap", "mask"]

    data = {
        suffix: [
            tmp_path
            / (
                f"sub-{subject}_task-faces_feature-taskBased_"
                "taskcontrast-facesGtScrambled_model-aggregateTaskBasedAcrossRuns_"
                f"contrast-intercept_{suffix}.nii.gz"
            )
            for subject in subjects
        ]
        for suffix in suffixes
    }

    data.update(
        {
            "subjects": subjects,
            "spreadsheet": tmp_path / "subjects_age_sex.csv",
        }
    )

    return data
