# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import numpy as np

from ...logging import logger
from ..spreadsheet import read_spreadsheet
from .base import Loader
from .direction import canonicalize_direction_code, parse_direction_str


class DatabaseMetadataLoader(Loader):
    def __init__(self, database, loader):
        self.database = database
        self.loader = loader

    def fill(self, fileobj, key):
        if self.database is None:
            return False

        value = None

        specfileobj = self.database.specfileobj(fileobj.path)
        if specfileobj is not None:
            metadata = getattr(specfileobj, "metadata", None)
            if metadata is not None:
                value = metadata.get(key)  # retrieve spec overrides

        if key == "phase_encoding_direction":
            direction = fileobj.tags.get("dir")
            if direction is not None:
                try:
                    pedir_code = parse_direction_str(direction)
                    value = canonicalize_direction_code(pedir_code, fileobj.path)
                except Exception as e:
                    logger.warning(
                        "Ignored exception when loading phase_encoding_direction:",
                        exc_info=e,
                    )

        if key == "echo_time_difference":  # calculate from associated files
            if fileobj.datatype == "fmap" and fileobj.suffix == "phasediff":
                filepath = fileobj.path
                magnitude1 = self.database.associations(filepath, suffix="magnitude1")
                magnitude2 = self.database.associations(filepath, suffix="magnitude2")
                if magnitude1 is not None and magnitude2 is not None:
                    if len(magnitude1) > 0 and len(magnitude2) > 0:  # two magnitude files
                        m1 = self.database.fileobj(next(iter(magnitude1)))
                        m2 = self.database.fileobj(next(iter(magnitude2)))
                        if self.loader.fill(m1, "echo_time") and self.loader.fill(m2, "echo_time"):
                            e1 = m1.metadata.get("echo_time")
                            e2 = m2.metadata.get("echo_time")
                            if e1 is not None and e2 is not None:
                                value = abs(e1 - e2)

        if key == "echo_time":  # calculate from associated file
            if fileobj.datatype == "fmap" and fileobj.suffix.startswith("phase"):
                filepath = fileobj.path
                suffix = dict(phase1="magnitude1", phase2="magnitude2").get(fileobj.suffix)
                if suffix is not None:
                    magnitude = self.database.associations(filepath, suffix=suffix)
                    if magnitude is not None and len(magnitude) > 0:
                        m = self.database.fileobj(next(iter(magnitude)))
                        if self.loader.fill(m, "echo_time"):
                            value = m.metadata.get("echo_time")

        if key == "slice_timing":
            slice_timing_file = fileobj.metadata.get("slice_timing_file")
            if slice_timing_file is not None:
                try:
                    spreadsheet = read_spreadsheet(slice_timing_file)
                    valuearray = np.ravel(spreadsheet.values).astype(np.float64)
                    value = list(valuearray)
                except Exception as e:
                    logger.warning(
                        f'Ignored exception when loading slice_timing_file "{slice_timing_file}":',
                        exc_info=e,
                    )

        if value is None:
            return False

        fileobj.metadata[key] = value
        return True
