# -*- coding: utf-8 -*-


from typing import Dict, List, Type, Union

from inflection import humanize

from ...ingest.glob import tag_parse
from ...model.file.anat import T1wFileSchema
from ...model.file.base import BaseFileSchema, File
from ...model.file.fmap import (
    BaseFmapFileSchema,
    EPIFmapFileSchema,
    PhaseDiffFmapFileSchema,
    PhaseFmapFileSchema,
)
from ...model.file.func import (
    BoldFileSchema,
    MatEventsFileSchema,
    TsvEventsFileSchema,
    TxtEventsFileSchema,
)
from ...model.file.ref import RefFileSchema
from ...model.file.schema import FileSchema
from ...model.tags import entities
from ...model.tags import entity_longnames as entity_display_aliases
from ...model.utils import get_schema_entities
from ...utils.path import split_ext
from ..utils.context import ctx
from .meta_data_steps import (
    CheckMetadataStep,
    CheckPhase1EchoTimeStep,
    CheckPhase2EchoTimeStep,
    CheckPhaseDiffEchoTimeDiffStep,
    CheckRepetitionTimeStep,
    CheckSpaceStep,
)

entity_colors = {
    "sub": "red",
    "ses": "green",
    "run": "magenta",
    "task": "cyan",
    "dir": "yellow",
    "condition": "orange",
    "acq": "purple",  # Changed to purple for uniqueness
    "echo": "brown",  # Changed to brown for uniqueness
    "desc": "red",  # there is only one entity when desc is used
}


def display_str(x):
    if x == "MNI152NLin6Asym":
        return "MNI ICBM 152 non-linear 6th Generation Asymmetric (FSL)"
    elif x == "MNI152NLin2009cAsym":
        return "MNI ICBM 2009c Nonlinear Asymmetric"
    elif x == "slice_encoding_direction":
        return "slice acquisition direction"
    return humanize(x)


class FilePatternStep:
    entity_display_aliases = entity_display_aliases
    header_str = ""
    ask_if_missing_entities: List[str] = list()
    required_in_path_entities: List[str] = list()

    filetype_str: str = "file"
    filedict: Dict[str, str] = {}
    schema: Union[Type[BaseFileSchema], Type[FileSchema]] = FileSchema
    next_step_type: None | type[CheckMetadataStep] = None

    def __init__(self, path="", app=None, callback=None, callback_message=None, id_key=""):
        self.entities = get_schema_entities(self.schema)  # Assumes a function to extract schema entities
        self.path = path
        self.app = app
        # setup
        self.fileobj: File | None = None

        self.callback = callback
        self.callback_message = callback_message  # if callback_message is not None else {self.filetype_str: []}
        # if callback_message is not None:
        #     self.callback_message.update({self.filetype_str: []})

        schema_entities = get_schema_entities(self.schema)
        schema_entities = [entity for entity in reversed(entities) if entity in schema_entities]  # keep order
        # convert to display
        self.schema_entities = [
            (self.entity_display_aliases[entity] if entity in self.entity_display_aliases else entity)
            for entity in schema_entities
        ]
        self.id_key = id_key

        # need original entities for this
        self.entity_colors_list = [entity_colors[entity] for entity in schema_entities]

        self.required_entities = [
            *self.ask_if_missing_entities,
            *self.required_in_path_entities,
        ]

    def _transform_extension(self, ext):
        return ext

    @property
    def get_entities(self):
        return self.schema_entities

    @property
    def get_entity_colors_list(self):
        return self.entity_colors_list

    @property
    def get_required_entities(self):
        return self.required_entities

    def check_extension(self, path):
        filedict = {**self.filedict, "path": path, "tags": {}}
        _, ext = split_ext(path)
        filedict["extension"] = self._transform_extension(ext)
        self.schema().load(filedict)

    async def push_path_to_context_obj(self, path):
        # run
        inv = {alias: entity for entity, alias in self.entity_display_aliases.items()}

        i = 0
        _path = ""
        for match in tag_parse.finditer(path):
            groupdict = match.groupdict()
            if groupdict.get("tag_name") in inv:
                _path += path[i : match.start("tag_name")]
                _path += inv[match.group("tag_name")]
                i = match.end("tag_name")

        _path += path[i:]
        path = _path

        # create file obj
        filedict = {**self.filedict, "path": path, "tags": {}}
        _, ext = split_ext(path)
        filedict["extension"] = self._transform_extension(ext)

        loadresult = self.schema().load(filedict)
        assert isinstance(loadresult, File), "Invalid schema load result"
        self.fileobj = loadresult

        # next
        ctx.spec.files.append(self.fileobj)
        ctx.database.put(ctx.spec.files[-1])  # we've got all tags, so we can add the fileobj to the index
        # ctx.cache[self.id_key]["files"][self.filetype_str] = self.fileobj
        ctx.cache[self.id_key]["files"] = self.fileobj  # type: ignore[assignment]

        if self.next_step_type is not None:
            print("---------------------------- going to the next_step_type", self.next_step_type)
            self.next_step_instance = self.next_step_type(
                app=self.app,
                callback=self.callback,
                callback_message=self.callback_message,
                id_key=self.id_key,
                sub_id_key=self.filetype_str,
            )
            await self.next_step_instance.run()
        else:
            pass


class AnatStep(FilePatternStep):
    required_in_path_entities = ["subject"]
    header_str = "T1-weighted image file pattern"
    filetype_str = "T1-weighted image"
    filedict = {"datatype": "anat", "suffix": "T1w"}

    schema = T1wFileSchema

    # def __init__(self, path=""):
    #     super().__init__(path=path)


class EventsStep(FilePatternStep):
    header_str = "Event file pattern"
    required_in_path_entities: List[str] = list()

    ask_if_missing_entities: List[str] = list()
    filedict = {"datatype": "func", "suffix": "events"}
    filetype_str = "event"

    def _transform_extension(self, ext):
        raise NotImplementedError()


class MatEventsStep(EventsStep):
    schema = MatEventsFileSchema

    def _transform_extension(self, ext):
        assert ext == ".mat"
        return ext


# next_step_type = CheckUnitsStep


class TxtEventsStep(EventsStep):
    schema = TxtEventsFileSchema
    required_in_path_entities = ["condition"]

    def _transform_extension(self, _):
        return ".txt"


class TsvEventsStep(EventsStep):
    schema = TsvEventsFileSchema

    def _transform_extension(self, _):
        return ".tsv"


class FmapFilePatternStep(FilePatternStep):
    bold_filedict = {"datatype": "func", "suffix": "bold"}
    filetype_str = "field map image"
    filetype_str = filetype_str
    filedict = {"datatype": "fmap"}


class FieldMapStep(FmapFilePatternStep):
    required_in_path_entities = ["subject"]
    header_str = "Path pattern of the field map image"
    filetype_str = "field map image"
    schema = BaseFmapFileSchema
    filedict = {**FmapFilePatternStep.filedict, "suffix": "fieldmap"}

    def __init__(self, path=""):
        super().__init__(path=path)


class EPIStep(FmapFilePatternStep):
    header_str = "Path pattern of the blip-up blip-down EPI image files"
    required_in_path_entities = ["subject"]

    filetype_str = "blip-up blip-down EPI image"
    schema = EPIFmapFileSchema
    filedict = {**FmapFilePatternStep.filedict, "suffix": "epi"}


class Magnitude1Step(FmapFilePatternStep):
    header_str = "Path pattern of first set of magnitude image"
    required_in_path_entities = ["subject"]

    filetype_str = "first set of magnitude image"
    filedict = {**FmapFilePatternStep.filedict, "suffix": "magnitude1"}
    schema = BaseFmapFileSchema


class Magnitude2Step(FmapFilePatternStep):
    header_str = "Path pattern of second set of magnitude image"
    required_in_path_entities = ["subject"]

    filetype_str = "second set of magnitude image"
    filedict = {**FmapFilePatternStep.filedict, "suffix": "magnitude2"}
    schema = BaseFmapFileSchema

    # next_step_type = m_next_step_type


class Phase1Step(FmapFilePatternStep):
    header_str = "Path pattern of the first set of phase image"
    required_in_path_entities = ["subject"]

    filetype_str = "first set of phase image"
    filedict = {**FmapFilePatternStep.filedict, "suffix": "phase1"}
    schema = PhaseFmapFileSchema

    next_step_type = CheckPhase1EchoTimeStep


class Phase2Step(FmapFilePatternStep):
    header_str = "Path pattern of the second set of phase image"
    required_in_path_entities = ["subject"]

    filetype_str = "second set of phase image"
    filedict = {**FmapFilePatternStep.filedict, "suffix": "phase2"}
    schema = PhaseFmapFileSchema

    next_step_type = CheckPhase2EchoTimeStep


class PhaseDiffStep(FmapFilePatternStep):
    header_str = "Path pattern of the phase difference image"
    required_in_path_entities = ["subject"]

    filetype_str = "phase difference image"
    filedict = {**FmapFilePatternStep.filedict, "suffix": "phasediff"}
    schema = PhaseDiffFmapFileSchema

    next_step_type = CheckPhaseDiffEchoTimeDiffStep


class BoldStep(FilePatternStep):
    ask_if_missing_entities = ["task"]
    required_in_path_entities = ["subject"]
    header_str = "BOLD image file pattern"

    schema = BoldFileSchema
    filetype_str = "BOLD image"
    filedict = {"datatype": "func", "suffix": "bold"}

    next_step_type = CheckRepetitionTimeStep


class AddAtlasImageStep(FilePatternStep):
    suffix, featurefield, dsp_str = "atlas", "atlases", "atlas"
    filetype_str = f"{dsp_str} image"
    filedict = {"datatype": "ref", "suffix": suffix}
    entity_display_aliases = {"desc": suffix}

    schema = RefFileSchema

    ask_if_missing_entities = ["desc"]
    required_in_path_entities = []

    next_step_type = CheckSpaceStep


class AddSpatialMapStep(FilePatternStep):
    suffix, featurefield, dsp_str = "map", "maps", "spatial map"
    filetype_str = f"{dsp_str} image"
    filedict = {"datatype": "ref", "suffix": suffix}
    entity_display_aliases = {"desc": suffix}

    schema = RefFileSchema

    ask_if_missing_entities = ["desc"]
    required_in_path_entities = []

    next_step_type = CheckSpaceStep


class AddBinarySeedMapStep(FilePatternStep):
    suffix, featurefield, dsp_str = "seed", "seeds", "binary seed mask"
    filetype_str = f"{dsp_str} image"
    filedict = {"datatype": "ref", "suffix": suffix}
    entity_display_aliases = {"desc": suffix}

    schema = RefFileSchema

    ask_if_missing_entities = ["desc"]
    required_in_path_entities = []

    next_step_type = CheckSpaceStep
