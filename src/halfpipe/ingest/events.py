# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.io import loadmat

from ..logging import logger
from ..model.file.base import File
from ..utils.path import split_ext
from .spreadsheet import read_spreadsheet

AnyFile = File | Path | str


def _extract_value(x: Any):
    if isinstance(x, np.ndarray):
        return _extract_value(x[0])
    return x


@dataclass
class ConditionFile:
    conditions: list[str]
    onsets: list[list[float]]
    durations: list[list[float]]

    def __init__(
        self,
        data: Iterable[tuple[AnyFile, str] | AnyFile] | AnyFile | None = None,
    ):
        self.conditions = list()
        self.onsets = list()
        self.durations = list()

        if isinstance(data, Iterable) and not isinstance(data, str):
            for x in data:
                self.parse(x)
        elif data is not None:
            self.parse(data)

    def parse(self, data: tuple[AnyFile, str] | AnyFile) -> None:
        path: Path | None = None
        condition: str | None = None
        extension: str | None = None

        # We have received a tuple of an FSL condition file and a condition name.
        if isinstance(data, tuple):
            data, condition = data
            extension = ".txt"

        # Ensure that we have a Path object. Extract the extension if necessary.
        if isinstance(data, (Path, str)):
            path = Path(data)
            if extension is None:
                _, extension = split_ext(path)

        elif isinstance(data, File):
            file = data
            path = Path(file.path)

            if extension is None:
                extension = file.extension
            if condition is None:
                condition = file.tags.get("condition")

        if extension == ".mat":
            self.parse_mat(path)
        elif extension == ".tsv":
            self.parse_tsv(path)
        elif extension == ".txt" or isinstance(condition, str):
            if not isinstance(condition, str):
                raise ValueError(f'Missing condition name for file "{path}"')
            self.parse_txt(condition, path)
        else:
            raise ValueError(f'Cannot read condition file "{path}" with extension "{extension}"')

    def parse_tsv(self, path: Path | str) -> None:
        data_frame = read_spreadsheet(path)
        if "trial_type" not in data_frame.columns:
            logger.warning(f'No "trial_type" column in "{path}"')
            return
        data_frame = data_frame.astype(dict(trial_type=str), copy=False)

        groupby = data_frame.groupby(by="trial_type")

        onsets_mapping = groupby["onset"].apply(list).to_dict()
        durations_mapping = groupby["duration"].apply(list).to_dict()

        for condition in groupby.groups.keys():
            assert isinstance(condition, str)

            self.conditions.append(condition)
            self.onsets.append(onsets_mapping[condition])
            self.durations.append(durations_mapping[condition])

    def parse_mat(self, path: Path | str) -> None:
        data = loadmat(path)
        if data is None:
            logger.warning(f'Cannot read condition file "{path}"')
            return

        names = np.squeeze(data["names"])
        durations = np.squeeze(data["durations"])
        onsets = np.squeeze(data["onsets"])

        for i, name in enumerate(names):
            condition = _extract_value(name)
            onset = np.ravel(onsets[i])
            duration = np.ravel(durations[i])

            # ensure type and shape
            coerce = np.zeros((onset.size, 2))
            coerce[:, 0] = onset
            coerce[:, 1] = duration

            self.conditions.append(condition)
            self.onsets.append(list(coerce[:, 0]))
            self.durations.append(list(coerce[:, 1]))

    def parse_txt(self, condition: str, path: Path | str) -> None:
        self.conditions.append(condition)

        try:
            data_frame = read_spreadsheet(path)

            data_frame.rename(
                columns=dict(zip(list(data_frame.columns)[:2], ["onsets", "durations"], strict=False)),
                inplace=True,
            )

            self.onsets.append(data_frame.onsets.tolist())
            self.durations.append(data_frame.durations.tolist())

        except Exception as e:  # unreadable or empty file
            logger.warning(f'Cannot read condition file "{path}"', exc_info=e)

            self.onsets.append([])  # fail gracefully
            self.durations.append([])

    def select(self, conditions: list[str]):
        conditions = list(map(str, conditions))  # make traits-free
        onsets = list()
        durations = list()

        for condition in conditions:
            if condition in self.conditions:
                i = self.conditions.index(condition)
                onsets.append(self.onsets[i])
                durations.append(self.durations[i])
            else:
                onsets.append(list())
                durations.append(list())

        return conditions, onsets, durations
