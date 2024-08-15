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
    filetype_str = "T1-weighted image"
    filedict = {"datatype": "anat", "suffix": "T1w"}
    schema = T1wFileSchema


class BoldSummaryStep(FilePatternSummaryStep):
    filetype_str = "BOLD image"
    filedict = {"datatype": "func", "suffix": "bold"}
    schema = BoldFileSchema


class FmapSummaryStep(FilePatternSummaryStep):
    filetype_str = "field map image"
    filedict = {"datatype": "fmap"}
    schema = BaseFmapFileSchema