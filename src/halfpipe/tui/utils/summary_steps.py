# -*- coding: utf-8 -*-

from typing import ClassVar, Dict, Type, Union

from ...model.file.anat import T1wFileSchema
from ...model.file.base import BaseFileSchema
from ...model.file.fmap import (
    BaseFmapFileSchema,
)
from ...model.file.func import (
    BoldFileSchema,
)
from ...model.file.schema import FileSchema
from ...model.tags import entity_longnames as entity_display_aliases
from ...model.utils import get_schema_entities
from ...utils.format import inflect_engine as p
from ..utils.context import ctx


def messagefun(database, filetype, filepaths, tagnames, entity_display_aliases: dict | None = None):
    """
    Parameters
    ----------
    database : DatabaseConnection
        An instance of the database connection used to retrieve tag values.
    filetype : str
        The type of files that are being queried.
    filepaths : list
        A list of file paths that are being processed.
    tagnames : list
        A list of tags to be checked in the filepaths.
    entity_display_aliases : dict, optional
        An optional dictionary for aliasing tag names for display.

    Returns
    -------
    str
        A message indicating the number of files found and the distribution of tag values.
    """
    entity_display_aliases = dict() if entity_display_aliases is None else entity_display_aliases
    message = ""
    if filepaths is not None:
        message = p.inflect(f"Found {len(filepaths)} {filetype} plural('file', {len(filepaths)})")
        if len(filepaths) > 0:
            n_by_tag = dict()
            for tagname in tagnames:
                tagvalset = database.tagvalset(tagname, filepaths=filepaths)
                if tagvalset is not None:
                    n_by_tag[tagname] = len(tagvalset)
            tagmessages = [
                p.inflect(f"{n} plural('{entity_display_aliases.get(tagname, tagname)}', {n})")
                for tagname, n in n_by_tag.items()
                if n > 0
            ]
            message += " "
            message += "for"
            message += " "
            message += p.join(tagmessages)
    return message


class FilePatternSummaryStep:
    """
    Class FilePatternSummaryStep:
        This class is used to generate a summary for a specific file pattern.
        It includes retrieving file paths from a database, generating a message regarding those files, and
        summarizing the information.

    Attributes
    ----------
    entity_display_aliases : ClassVar[Dict]
        A dictionary containing aliases for displaying various entities.
    filetype_str : ClassVar[str]
        A string representing the type of file.
    filedict : Dict[str, str]
        A dictionary that is used to retrieve file paths from the database.
    schema : Union[Type[BaseFileSchema], Type[FileSchema]]
        A schema to extract schema entities.

    Methods
    -------
    __init__():
        Initializes the FilePatternSummaryStep object by extracting schema entities, retrieving file paths from
        the database, and generating a message.

    get_message() -> str:
        Returns the generated message.

    get_summary() -> Dict[str, Union[str, List[str]]]:
        Returns a summary dictionary containing the generated message and the file paths.
    """

    entity_display_aliases: ClassVar[Dict] = entity_display_aliases

    filetype_str: ClassVar[str] = "file"
    filedict: Dict[str, str] = dict()
    schema: Union[Type[BaseFileSchema], Type[FileSchema]] = FileSchema

    def __init__(self):
        self.entities = get_schema_entities(self.schema)  # Assumes a function to extract schema entities

        # Assuming ctx and database are accessible here
        self.filepaths = ctx.database.get(**self.filedict)
        self.message = messagefun(
            ctx.database,
            self.filetype_str,
            self.filepaths,
            self.entities,
            entity_display_aliases,  # This should be defined somewhere accessible
        )

    @property
    def get_message(self):
        return self.message

    @property
    def get_summary(self):
        return {"message": self.message, "files": self.filepaths}


class AnatSummaryStep(FilePatternSummaryStep):
    """
    AnatSummaryStep
        Class representing a summary step for anatomical (T1-weighted) imaging files.

    Attributes
    ----------
    filetype_str : str
        Descriptive string for the type of file, indicating it is a "T1-weighted image".
    filedict : dict
        Dictionary defining the file pattern components, here specifying that the `datatype` is "anat" and the `suffix`
        is "T1w".
    schema : T1wFileSchema
        Schema class used for validating and processing T1-weighted image files.
    """

    filetype_str = "T1-weighted image"
    filedict = {"datatype": "anat", "suffix": "T1w"}
    schema = T1wFileSchema


class BoldSummaryStep(FilePatternSummaryStep):
    """
    Class BoldSummaryStep
        Class representing a summary step for functional BOLD files.

    Attributes
    ----------
    filetype_str : str
        Descriptive string for the type of file, indicating it is a BOLD image.
    filedict : dict
        Dictionary defining the file pattern components, here specifying that the `datatype` is "func"
        and the `suffix` is "bold".
    schema : BoldFileSchema
        Schema class used for validating and processing BOLD image files.
    """

    filetype_str = "BOLD image"
    filedict = {"datatype": "func", "suffix": "bold"}
    schema = BoldFileSchema


class FmapSummaryStep(FilePatternSummaryStep):
    """
    A class representing a summary step for field map images.

    Attributes
    ----------
    filetype_str : str
        Descriptive string for the type of file, indicating it is a field map image.
    filedict : dict
        Dictionary defining the file pattern components, here specifying that the `datatype` is "fmap" .
    schema : BaseFmapFileSchema
        A schema class that defines the structure and constraints of the field map files.
    """

    filetype_str = "field map image"
    filedict = {"datatype": "fmap"}
    schema = BaseFmapFileSchema
