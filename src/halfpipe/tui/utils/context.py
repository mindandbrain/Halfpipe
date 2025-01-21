# -*- coding: utf-8 -*-
# from .ui.components import SingleChoiceInputView, SpacerView, TextElement, TextView
from collections import defaultdict
from pathlib import Path
from typing import Any

# class Context:
# def __init__(self) -> None:
# spec_schema = SpecSchema()
# spec = spec_schema.load(spec_schema.dump({}), partial=True)
# assert isinstance(spec, Spec)
# self.spec: Spec = spec  # initialize with defaults
# self.database = Database(self.spec)
# self.workdir: Path | None = None
# self.use_existing_spec = False
# self.debug = False
# self.already_checked: set[str] = set()
# def put(self, fileobj):
# self.database.put(fileobj)
# return len(self.spec.files) - 1
from ...ingest.database import Database

# from ..logging import logger
from ...model.spec import Spec, SpecSchema
from ...model.tags import entities


# This is a singleton!
class Context:
    """
    Context class to manage the application’s state and configuration.

    This class implements the singleton pattern to ensure only one instance manages the spec, database,
    working directory, cache, and other configuration aspects. It initializes the configuration from a default
    spec schema and sets up the database connection.

    Attributes
    ----------
    _instance: Context
        Singleton instance of the Context class.
    _initialized: bool
        Flag to check if the instance has already been initialized.
    spec: Spec
        Specification object loaded with default values.
    database: Database
        Database instance initialized with the spec.
    workdir: Path or None
        Working directory path, initially set to None.
    use_existing_spec: bool
        Flag to determine if an existing spec should be used.
    debug: bool
        Debug mode flag.
    already_checked: set of str
        Set to keep track of already checked items.
    cache: defaultdict
        Nested default dictionary to maintain cache.
    available_images: dict
        Dictionary storing available images.

    Methods
    -------
    __new__(cls, *args, **kwargs)
        Creates a new instance if none exists, else returns the existing instance.

    __init__(self)
        Initializes the Context instance with default values.

    put(self, fileobj)
        Puts a file object into the database and returns the number of spec files.

    refresh_available_images(self)
        Refreshes the dictionary of available images by querying the database.

    get_available_images(self)
        Property to retrieve the available images dictionary.
    """

    _instance = None
    _initialized: bool

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Context, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        spec_schema = SpecSchema()
        spec = spec_schema.load(spec_schema.dump({}), partial=True)
        assert isinstance(spec, Spec)
        self.spec: Spec = spec  # initialize with defaults
        self.database = Database(self.spec)
        self.workdir: Path | None = None
        self.use_existing_spec = False
        self.debug = False
        self.already_checked: set[str] = set()
        self._initialized = True
        self.cache: defaultdict[str, defaultdict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
        self.available_images: dict = {}

    def put(self, fileobj):
        self.database.put(fileobj)
        return len(self.spec.files) - 1

    def refresh_available_images(self):
        bold_filedict = {"datatype": "func", "suffix": "bold"}
        filepaths = self.database.get(**bold_filedict)

        db_entities, db_tags_set = self.database.multitagvalset(entities, filepaths=filepaths, min_set_size=0)

        if db_entities != []:
            self.available_images[db_entities[0]] = sorted(list({t[0] for t in db_tags_set}))

    @property
    def get_available_images(self):
        return self.available_images


ctx = Context()
