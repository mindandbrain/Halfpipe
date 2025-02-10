# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from ..ingest.database import Database
from ..ingest.metadata.direction import canonicalize_direction_code
from ..logging import logger
from ..utils.format import inflect_engine as pe


def check_pes(epi_fmaps, pe_dir):
    """Check whether there are images with matched PE.
    Note: Function backported from sdcworkflows 1.3.5."""
    opposed_pe = False
    matched_pe = False

    for _, fmap_pe in epi_fmaps:
        if fmap_pe == pe_dir:
            matched_pe = True
        elif fmap_pe[0] == pe_dir[0]:
            opposed_pe = True

    if not opposed_pe:
        raise ValueError("""\
None of the discovered fieldmaps has the right phase encoding direction. \
This is possibly a problem with metadata. If not, rerun with \
``--ignore fieldmaps`` to skip the distortion correction step.""")

    return matched_pe


def collect_pe_dir(database: Database, c: str):
    database.fillmetadata("phase_encoding_direction", [c])
    pe_dir = canonicalize_direction_code(
        database.metadata(c, "phase_encoding_direction"),
        c,
    )
    return pe_dir


def collect_fieldmaps(database: Database, bold_file_path: str, silent: bool = False) -> list[str]:
    bold_file_tags = database.tags(bold_file_path)
    if bold_file_tags is None:
        return list()
    bold_file_tags = bold_file_tags.copy()  # Ensure modification has no side effects

    sub = bold_file_tags.get("sub")
    if sub is None:
        return list()
    # Ensure same subject and datatype
    filters: dict[str, str] = dict(sub=sub, datatype="fmap")
    # If applicable, ensure fmaps from same session
    session = bold_file_tags.get("ses")
    if session is not None:
        filters.update(dict(ses=session))
    # Do not filter by `dir` tag, because we might miss compatible field maps otherwise
    if "dir" in bold_file_tags:
        del bold_file_tags["dir"]

    matching_files = database.associations2(bold_file_tags, filters)
    if matching_files is None:
        return list()
    candidates: set[str] = set(matching_files)

    if candidates is None:
        return list()

    candidates = set(candidates)

    # Filter phase maps
    magnitude_map: dict[str, list[str]] = {
        "phase1": ["magnitude1", "magnitude2"],
        "phase2": ["magnitude1", "magnitude2"],
        "phasediff": ["magnitude1", "magnitude2"],
        "fieldmap": ["magnitude"],
    }

    incomplete: set[str] = set()
    for c in candidates:
        suffix = database.tagval(c, "suffix")
        assert isinstance(suffix, str)
        if suffix not in magnitude_map:
            continue
        magnitude: list[str] = magnitude_map[suffix]

        has_magnitude = any(database.tagval(c, "suffix") in magnitude for c in candidates)
        if not has_magnitude:
            incomplete.add(c)

    if len(incomplete) > 0:
        if silent is not True:
            incomplete_str = pe.join(sorted(incomplete))
            logger.info(f"Skipping field maps {incomplete_str} due to missing magnitude images")
        candidates -= incomplete

    # Filter pepolar
    epi_fmaps = list()
    for c in candidates:
        suffix = database.tagval(c, "suffix")
        if not isinstance(suffix, str):
            continue
        if suffix != "epi":
            continue

        epi_fmaps.append((c, collect_pe_dir(database, c)))

    if len(epi_fmaps) > 0:
        try:
            check_pes(epi_fmaps, collect_pe_dir(database, bold_file_path))
        except ValueError:
            if silent is not True:
                incomplete_str = pe.join(sorted(f'"{c}" with direction {dir}' for c, dir in epi_fmaps))
                logger.info(f"Skipping field maps {incomplete_str} because they do not have matched phase encoding directions")
            candidates -= set(c for c, _ in epi_fmaps)

    return sorted(candidates)
