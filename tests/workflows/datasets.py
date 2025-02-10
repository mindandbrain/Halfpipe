# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:


from dataclasses import dataclass
from pathlib import Path

import datalad.api as dl
import openneuro as on

from halfpipe.file_index.bids import BIDSIndex
from halfpipe.model.file.base import File
from halfpipe.model.file.schema import FileSchema


@dataclass
class Dataset:
    name: str
    url: str
    openneuro_id: str
    openneuro_url: str
    paths: list[str]

    @property
    def subject_ids(self) -> set[str]:
        index = BIDSIndex()
        for path_str in self.paths:
            path = Path(path_str)  # Convert string path to Path object
            index.put(path)
        return index.get_tag_values("sub")

    def download(self, tmp_path: Path) -> File:
        ds = dl.clone(source=self.url, path=str(tmp_path))
        for path in self.paths:
            ds.get(path)
        return FileSchema().load(dict(datatype="bids", path=str(tmp_path)))

    def download_openneuro(self, tmp_path: Path) -> File:
        for file_path in self.paths:
            on.download(dataset=self.openneuro_id, include=file_path, target_dir=tmp_path)
        return FileSchema().load(dict(datatype="bids", path=str(tmp_path)))


datasets: list[Dataset] = [
    # Dataset(
    #     name="on_harmony",  # single-band scan
    #     openneuro_id="ds004712",
    #     openneuro_url="https://github.com/OpenNeuroDatasets/ds004712/blob/master",
    #     url="https://github.com/OpenNeuroDatasets/ds004712.git",
    #     paths=[
    #         "sub-13192/ses-NOT3GEM001/func/sub-13192_ses-NOT3GEM001_task-rest_acq-resopt2_bold.nii.gz",
    #         "sub-13192/ses-NOT3GEM001/anat/sub-13192_ses-NOT3GEM001_T1w.json",
    #         "sub-13192/ses-NOT3GEM001/anat/sub-13192_ses-NOT3GEM001_T1w.nii.gz",
    #     ],
    # ),
    Dataset(
        name="emory",  # multiband
        openneuro_id="ds003540",
        openneuro_url="https://github.com/OpenNeuroDatasets/ds003540/blob/master",
        url="https://github.com/OpenNeuroDatasets/ds003540.git",
        paths=[
            "sub-01/anat/sub-01_T1w.nii.gz",
            "sub-01/func/sub-01_task-rest_acq-MB8_bold.nii.gz",
            "sub-01/func/sub-01_task-rest_acq-MB8_sbref.nii.gz",
        ],
    ),
    # Dataset(
    #     name="panikratova",  # New 1.5 Tesla
    #     openneuro_id="ds002422",
    #     openneuro_url="https://github.com/OpenNeuroDatasets/ds002422.git",
    #     url="https://github.com/OpenNeuroDatasets/ds002422",
    #     paths=[
    #         "sub-09/func/sub-09_task-rest_bold.nii.gz",
    #         "sub-09/func/sub-09_task-rest_bold.json",
    #         "sub-09/anat/sub-09_T1w.nii",
    #         "T1w.json",
    #     ],
    # ),
    # Dataset(
    #     name="sleepy_brain",  # Has fieldmaps
    #     openneuro_id="ds000201",
    #     openneuro_url="https://github.com/OpenNeuroDatasets/ds000201/blob/master/",
    #     url="https://github.com/OpenNeuroDatasets/ds000201.git",
    #     paths=[
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_magnitude2.nii.gz",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_magnitude1.nii.gz",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_phase1.nii.gz",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_phase2.nii.gz",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_magnitude1.json",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_magnitude2.json",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_phase1.json",
    #         "sub-9040/ses-1/fmap/sub-9040_ses-1_phase2.json",
    #         "sub-9040/ses-1/anat/sub-9040_ses-1_T1w.json",
    #         "sub-9040/ses-1/anat/sub-9040_ses-1_T1w.nii.gz",
    #         "sub-9040/ses-1/func/sub-9040_ses-1_task-rest_bold.nii.gz",
    #         "sub-9040/ses-1/func/sub-9040_ses-1_task-rest_bold.json",
    #     ],
    # ),
]
