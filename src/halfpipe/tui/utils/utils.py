# -*- coding: utf-8 -*-


import os
import re
import shutil
from datetime import datetime

from ...collect.events import collect_events
from ...ingest.events import ConditionFile
from ...model.filter import FilterSchema
from .context import ctx


def extract_name_part(template_path, file_path, suffix="atlas"):
    """
    Parameters
    ----------
    template_path : str
        The template string that includes a placeholder for dynamic matching.
    file_path : str
        The actual file path from which a part will be extracted based on the template.
    suffix : str, optional
        The suffix used to create the placeholder in the template_path (default is "atlas").
    """
    # Create a regex pattern dynamically based on the template
    placeholder = f"{{{suffix}}}"
    pattern = re.escape(template_path).replace(re.escape(placeholder), rf"(?P<{suffix}>.+)")
    #
    # Search for the atlas part using the regex pattern
    match = re.search(pattern, file_path)
    #
    if match:
        return match.group(suffix)
    else:
        return None  # Return None if no match is found


def extract_conditions(entity, values):
    """
    Parameters
    ----------
    entity : str
        The entity for which conditions are being extracted.
    values : list
        The values associated with the entity.

    Returns
    -------
    dict
        The conditions obtained after applying the filter.
    """
    filter_schema = FilterSchema()
    _filter = filter_schema.load(
        {
            "type": "tag",
            "action": "include",
            "entity": entity,
            "values": values,
        }
    )
    return get_conditions(_filter)


def get_conditions(_filter):
    """
    Parameters
    ----------
    _filter : any
        The filter criteria used to find bold file paths.

    Returns
    -------
    conditions : list of str
        A list of unique conditions extracted from event file paths associated
        with the bold file paths.
    """
    bold_file_paths = find_bold_file_paths(_filter)

    conditions: list[str] = list()
    seen = set()
    for bold_file_path in bold_file_paths:
        event_file_paths = collect_events(ctx.database, bold_file_path)
        if event_file_paths is None:
            continue

        if event_file_paths in seen:
            continue

        cf = ConditionFile(data=event_file_paths)
        for condition in cf.conditions:  # maintain order
            if condition not in conditions:
                conditions.append(condition)

        seen.add(event_file_paths)
    return conditions


def find_bold_file_paths(_filter):
    """
    Parameters
    ----------
    _filter : callable or None
        A filter function to apply to the set of BOLD file paths retrieved
        from the database. If None, no filtering is applied.

    Returns
    -------
    set
        A set of BOLD file paths after applying the optional filter.

    Raises
    ------
    ValueError
        If no BOLD files are found in the database.
    """
    bold_file_paths = ctx.database.get(datatype="func", suffix="bold")

    if bold_file_paths is None:
        raise ValueError("No BOLD files in database")

    bold_file_paths = set(bold_file_paths)

    if _filter is not None:
        bold_file_paths = ctx.database.applyfilters(bold_file_paths, [_filter])

    return bold_file_paths


def tag_the_string(tagvals):
    """
    Parameters
    ----------
    tagvals : list
        A list of string elements that need to be wrapped in double quotes.

    Returns
    -------
    list
        A new list with each original string element wrapped in double quotes.
    """
    return [f'"{tagval}"' for tagval in tagvals]


def copy_and_rename_file(src_file):
    # Get the directory, filename, and extension
    dir_name, file_name = os.path.split(src_file)
    file_base, file_ext = os.path.splitext(file_name)

    # Create a timestamp in YYYY-MM-DD_HH-MM format
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Create the new filename
    new_file_name = f"{file_base}_{timestamp}{file_ext}"
    new_file_path = os.path.join(dir_name, new_file_name)

    # Copy the file and rename it
    shutil.copy(src_file, new_file_path)

    return new_file_path
