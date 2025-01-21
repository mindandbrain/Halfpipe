# -*- coding: utf-8 -*-
# conftest.py
import os
import shutil
from pathlib import Path

import pytest

from halfpipe import resource
from halfpipe.tui.base import MainApp  # Ensure path aligns with your project structure

from ..workflows.datasets import Dataset  # Adjust this import path as needed


# Custom fixture that returns a specific path, this is needed so that the path in the snapshot is always the same
# If the path was variable then the snapshot would yield failure.
@pytest.fixture(scope="session")
def fixed_tmp_path() -> Path:
    path = Path("/tmp/tui_test/")
    path.mkdir(parents=True, exist_ok=True)  # Ensure the path exists
    return path
    # Clean up after the test, is this needed?
    # shutil.rmtree(path)


# Define the fixture with module scope, one subject, three tasks
@pytest.fixture(scope="session")
def downloaded_data_path(fixed_tmp_path) -> Path:
    dataset = Dataset(
        name="PIOP1",
        openneuro_id="ds002785",
        openneuro_url="https://openneuro.org/datasets/ds002785/versions/2.0.0",
        url="https://github.com/OpenNeuroDatasets/ds002785.git",
        paths=[
            "sub-0001/anat",
            "sub-0001/func/sub-0001_task-anticipation_acq*",
            "sub-0001/func/sub-0001_task-workingmemory_acq*",
            "sub-0001/func/sub-0001_task-restingstate_acq*",
        ],
    )

    data_path = fixed_tmp_path / "ds002785/"
    dataset.download(data_path)
    return data_path


@pytest.fixture(scope="session")
def atlases_maps_seed_images_path(fixed_tmp_path) -> Path:
    # set atlases, seed maps and spatial maps
    test_online_resources = {
        "FIND_ica_maps_2009.nii.gz": "https://drive.google.com/file/d/1XnFGm9aCcTIuXgKZ71fDqATBJWAxkInO/view?usp=drive_link",
        "tpl-MNI152NLin2009cAsym_atlas-schaefer2011Combined_dseg.nii": "https://drive.google.com/file/d/1CR0rjbznad-tkfVc1vrGKsKJg5_nrf5E/view?usp=drive_link",
        "tpl-MNI152NLin2009cAsym_atlas-brainnetomeCombined_dseg.nii": "https://drive.google.com/file/d/1MYF4VaZrWmQXL1Jl3ZWMg1tWaKBfPo4W/view?usp=drive_link",
        "R_vmPFC_seed_2009.nii.gz": "https://drive.google.com/file/d/16L_HXOrrMqw08BdGTOh7RTErNTVytyvS/view?usp=drive_link",
        "R_vlPFC_pt_seed_2009.nii.gz": "https://drive.google.com/file/d/1fNr8ctHpTN8XJn95mclMxTetKdpbdddV/view?usp=drive_link",
        "R_vlPFC_po_seed_2009.nii.gz": "https://drive.google.com/file/d/1te1g3tpFaHdjx8GyZ1myMg_ayaHXPYKO/view?usp=drive_link",
    }

    resource.resource_dir = Path(fixed_tmp_path / "atlases_maps_seed_images")
    resource.resource_dir.mkdir(exist_ok=True, parents=True)
    resource.online_resources.update(test_online_resources)

    for item in test_online_resources:
        resource.get(item)

    return resource.resource_dir


@pytest.fixture(scope="session")
def work_dir_path(fixed_tmp_path) -> Path:
    return fixed_tmp_path / "work_dir/"


@pytest.fixture(scope="session")
def spec_file_dir_path(fixed_tmp_path) -> Path:
    source_dir = "./spec_file_for_load_test"
    destination_dir = fixed_tmp_path / "spec_file_for_load_test/"
    if os.path.exists(destination_dir):
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)
    return destination_dir


@pytest.fixture(scope="session")
def t1_path_pattern(downloaded_data_path) -> Path:
    return downloaded_data_path / "sub-{subject}/anat/sub-{subject}_T1w.nii.gz"


@pytest.fixture(scope="session")
def bold_path_pattern(downloaded_data_path) -> Path:
    return downloaded_data_path / "sub-{subject}/func/sub-{subject}_task-{task}_bold.nii.gz"


@pytest.fixture(scope="session")
def event_path_pattern(downloaded_data_path) -> Path:
    return downloaded_data_path / "sub-{subject}/func/sub-{subject}_task-{task}_events.tsv"


# should yield a fresh instance each time, but apparently it does not
@pytest.fixture(scope="function")
def start_app():
    return MainApp()
