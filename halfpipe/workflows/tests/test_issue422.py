# -*- coding: utf-8 -*-
import json
import os

import pytest  # noqa


def test_issue422(tmp_path):
    """Recreating scenario https://github.com/HALFpipe/HALFpipe/issues/422"""
    bids_path = tmp_path / "bids"

    fmap_path = bids_path / "rawdata" / "sub-003" / "fmap"

    files = [
        "sub-003_acq-SeqMm3Tr2000_dir-mushroom_run-1.nii.gz",
        "sub-003_acq-SeqMm3Tr2000_dir-j_run-1.nii.gz",
        "sub-003_task-mushroom_acq-SeqMm3Tr2000_run-1_bold.nii.gz",
        "sub-003_dir-_epi.json",
        "sub-003_dir-j_epi.json",
    ]

    for i in files:
        os.path.join(fmap_path, i)

    for file in os.listdir(fmap_path):
        if "json" in file:
            with open(fmap_path / file, "r") as json_file:
                data = json.load(json_file)
            data["PhaseEncodingDirection"] = "j-"
            data["IntendedFor"] = [
                "func/sub-003_task-mushroom_acq-SeqMm3Tr2000_run-1_bold.nii.gz"
            ]
            with open(fmap_path / file, "w") as json_file:
                json.dump(data, json_file)
