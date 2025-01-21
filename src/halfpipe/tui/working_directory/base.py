# -*- coding: utf-8 -*-
# ok to review

import copy
import os
from collections import defaultdict

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from ...model.spec import load_spec
from ..feature_widgets.features import AtlasBased, DualReg, PreprocessedOutputOptions, SeedBased, TaskBased
from ..utils.confirm_screen import Confirm
from ..utils.context import ctx
from ..utils.event_file_widget import AtlasFilePanel, EventFilePanel, SeedMapFilePanel, SpatialMapFilePanel
from ..utils.filebrowser import FileBrowser, path_test_for_bids
from ..utils.non_bids_file_itemization import FileItem
from ..utils.utils import copy_and_rename_file


class WorkDirectory(Widget):
    """
    Class for managing the working directory selection and initialization, specifically for output storage
    and loading configurations from existing 'spec.json' files.

    Parameters
    ----------
    id : str | None, optional
        Identifier for the widget, by default None.
    classes : str | None, optional
        Classes for CSS styling, by default None.


    Methods
    -------
    compose()
        Composes the widgets for the working directory interface.

    on_mount()
        Sets up the widget after it has been added to the DOM.

    _on_file_browser_changed(message)
        Handles file browser's changed event, including verifying selected directory and loading configuration
        from 'spec.json'.

    working_directory_override(override)
        Manages overriding an existing spec file, if one is found in the selected directory.

    existing_spec_file_decision(load)
        Manages user decision whether to load an existing spec file or override it.

    load_from_spec()
        Loads settings from 'spec.json' and updates the context cache.

    cache_file_patterns()
        Caches data from 'spec.json' into context and creates corresponding widgets.

    mount_features()
        Mounts feature selection widgets based on the spec file.

    on_worker_state_changed(event)
        Handles state change events for workers, progressing through stages of loading.

    mount_file_panels()
        Initializes file panels for various file types (events, atlas, seed, spatial maps).
    """

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)

    def compose(self) -> ComposeResult:
        work_directory = Vertical(
            Static(
                "Set path to the working directory. Here all output will be stored. By selecting a directory with existing \
spec.json file it is possible to load the therein configuration.",
                id="description",
            ),
            FileBrowser(path_to="WORKING DIRECTORY", id="work_dir_file_browser"),
            id="work_directory",
            classes="components",
        )
        work_directory.border_title = "Select working directory"

        yield work_directory

    @on(FileBrowser.Changed)
    async def _on_file_browser_changed(self, message: Message):
        """The FileBrowser itself makes checks over the selected working directory validity. If it passes then we get here
        and no more checks are needed.
        """
        # Change border to green
        self.get_widget_by_id("work_dir_file_browser").styles.border = ("solid", "green")
        # add flag signaling that the working directory was set
        self.app.flags_to_show_tabs["from_working_dir_tab"] = True
        self.app.show_hidden_tabs()

        async def working_directory_override(override):
            """Function about overriding the found existing spec files"""
            if override:
                # make a backup copy from the original spec file
                if ctx.workdir is not None:
                    copy_and_rename_file(os.path.join(ctx.workdir, "spec.json"))
            else:
                self.get_widget_by_id("work_dir_file_browser").update_input(None)
                ctx.workdir = None

        async def existing_spec_file_decision(load):
            """Function making user aware that there is an existing spec file in the selected working directory
            and whether he/she wants to load it.
            """
            if load:
                await self.load_from_spec()
            else:
                self.app.push_screen(
                    Confirm(
                        "This action will override the existing spec in the selected working directory. Are you sure?",
                        title="Override existing working directory",
                        id="confirm_override_spec_file_modal",
                        classes="confirm_warning",
                    ),
                    working_directory_override,
                )

        # add path to context object
        ctx.workdir = message.selected_path
        # Load the spec and by this we see whether there is existing spec file or not
        self.existing_spec = load_spec(workdir=ctx.workdir)
        if self.existing_spec is not None:
            self.app.push_screen(
                Confirm(
                    "Existing spec file was found! Do you want to load the settings or override the working directory?",
                    title="Spec file found",
                    left_button_text="Load",
                    right_button_text="Override",
                    id="confirm_spec_load_modal",
                    classes="confirm_warning",
                ),
                existing_spec_file_decision,
            )

    async def load_from_spec(self):
        """Feed the user_selections_dict with settings from the json file via the context object."""
        # First feed the cache
        if self.existing_spec is not None:  # Add this check
            global_settings = self.existing_spec.global_settings
            files = self.existing_spec.files
            settings = self.existing_spec.settings
            features = self.existing_spec.features
            models = self.existing_spec.models

            ctx.spec.global_settings = global_settings
            for fileobj in files:
                ctx.put(fileobj)
            ctx.spec.settings = settings
            ctx.spec.features = features
            ctx.spec.models = models

            self.cache_file_patterns()

    @work(exclusive=True, name="cache_file_worker")
    async def cache_file_patterns(self):
        data_input_widget = self.app.get_widget_by_id("input_data_content")
        preprocessing_widget = self.app.get_widget_by_id("preprocessing_content")
        self.feature_widget = self.app.get_widget_by_id("feature_selection_content")
        self.model_widget = self.app.get_widget_by_id("models_content")

        # The philosophie here is that we copy the data from the existing spec file to the context cache and then create
        # corresponding widgets. Through these widgets then it should be possible to further modify the spec file.
        # The created widgets should avoid using step and meta classes upon creation as these triggers various user choice
        # modals.
        if self.existing_spec is not None:
            self.app.get_widget_by_id("input_data_content").toggle_bids_non_bids_format(False)
            self.event_file_objects = []
            self.atlas_file_objects = []
            self.seed_map_file_objects = []
            self.spatial_map_file_objects = []

            preprocessing_widget.default_settings = self.existing_spec.global_settings
            preprocessing_widget = preprocessing_widget.refresh(recompose=True)

            for f in self.existing_spec.files:
                # In the spec file, subject is abbreviated to 'sub' and atlas, seed and map is replaced by desc,
                # here we replace it back for the consistency.
                f.__dict__["path"] = f.__dict__["path"].replace("{sub}", "{subject}")
                if f.datatype == "bids":
                    ctx.cache["bids"]["files"] = f.path
                    data_input_widget.get_widget_by_id("data_input_file_browser").update_input(f.path)
                    # this is the function used when we are loading bids data files, in also checks if the data
                    # folder contains bids files, and if yes, then it also extracts the tasks (images)
                    path_test_for_bids(f.path)
                    self.app.get_widget_by_id("input_data_content").toggle_bids_non_bids_format(True)
                # need to create a FileItem widgets for all non-bids files
                elif f.suffix == "bold":
                    message_dict = {i: [str(f.metadata[i])] for i in f.metadata if i == "repetition_time"}
                    widget_name = await data_input_widget.add_bold_image(
                        load_object=f, message_dict=message_dict, execute_pattern_class_on_mount=False
                    )
                    ctx.cache[widget_name]["files"] = f
                elif f.suffix == "T1w":
                    widget_name = await data_input_widget.add_t1_image(
                        load_object=f, message_dict=None, execute_pattern_class_on_mount=False
                    )
                    ctx.cache[widget_name]["files"] = f
                elif f.suffix == "events":
                    self.event_file_objects.append(f)
                elif f.suffix == "atlas":
                    f.__dict__["path"] = f.__dict__["path"].replace("{desc}", "{atlas}")
                    self.atlas_file_objects.append(f)
                elif f.suffix == "seed":
                    f.__dict__["path"] = f.__dict__["path"].replace("{desc}", "{seed}")
                    self.seed_map_file_objects.append(f)
                elif f.suffix == "map":
                    f.__dict__["path"] = f.__dict__["path"].replace("{desc}", "{map}")
                    self.spatial_map_file_objects.append(f)

            ctx.refresh_available_images()
            data_input_widget.update_summaries()
            if ctx.get_available_images == {}:
                self.data_input_success = await self.app.push_screen_wait(
                    Confirm(
                        "No bold files found! The data input directory in \n"
                        "the spec.json seems to be not available on your computer!",
                        title="Error",
                        left_button_text=False,
                        right_button_text="OK",
                        id="input_data_directory_error_modal",
                        classes="confirm_error",
                    )
                )
                # clear all inputs, basically restart the inputs on the TUI
                for file_item in self.app.walk_children(FileItem):
                    file_item.remove()
                ctx.cache = defaultdict(lambda: defaultdict(dict))
                self.app.flags_to_show_tabs["from_input_data_tab"] = False
                self.app.flags_to_show_tabs["from_working_dir_tab"] = False
                self.app.hide_tabs()
                self.get_widget_by_id("work_dir_file_browser").update_input("")
                ctx.workdir = None
            else:
                self.data_input_success = True

    @work(exclusive=True, name="feature_worker")
    async def mount_features(self):
        # feature_widget = self.app.get_widget_by_id("feature_selection_content")
        feature_widget = self.feature_widget

        setting_feature_map = {}
        if self.existing_spec is not None:
            for feature in self.existing_spec.features:
                ctx.cache[feature.name]["features"] = copy.deepcopy(feature.__dict__)
                # if feature.type != 'falff':
                setting_feature_map[feature.__dict__["setting"]] = feature.name
                # else:
                #     setting_feature_map[feature.__dict__["unfiltered_setting"]] = feature.name

            for setting in self.existing_spec.settings:
                # the feature settings in the ctx.cache are under the 'feature' key, to match this properly
                # setting['name'[ is used without last 7 letters which are "Setting" then it is again the feature name

                if setting["output_image"] is not True:
                    # In case of falff, there is also unfiltered setting which is essentially the same as normal setting
                    # but without the bandpass filter. So we put only the normal setting into the cache because in the run
                    # tab the unfiltered setting will be created automatically form the normal setting.
                    if setting["name"] in setting_feature_map:
                        ctx.cache[setting_feature_map[setting["name"]]]["settings"] = copy.deepcopy(setting)
                else:
                    ctx.cache[setting["name"]]["features"] = {}
                    ctx.cache[setting["name"]]["settings"] = copy.deepcopy(setting)

                if setting["name"] in setting_feature_map:
                    # settings = ctx.cache.get(setting_feature_map[setting["name"]], {}).get("settings", {})
                    # feature = ctx.cache.get(setting_feature_map[setting["name"]], {}).get("features", {})
                    cache_entry: dict = ctx.cache.get(setting_feature_map[setting["name"]], {})
                    if isinstance(cache_entry, dict):
                        settings = cache_entry.get("settings", {})
                        feature = cache_entry.get("features", {})
                    else:
                        settings = {}
                        feature = {}
                    # Add default smoothing settings if missing
                    if feature["type"] == "falff" or feature["type"] == "reho":
                        feature.setdefault("smoothing", {"fwhm": None})
                    else:
                        settings.setdefault("smoothing", {"fwhm": None})

                    settings.setdefault("grand_mean_scaling", {"mean": None})
                    print("ssssssssssssssssssssssssssssssssssssssssss settings", settings)
                    settings.setdefault("bandpass_filter", {"type": None})

            # Then create the widgets
            for top_name in ctx.cache:
                if ctx.cache[top_name]["features"] != {}:
                    name = ctx.cache[top_name]["features"]["name"]
                    await feature_widget.add_new_feature([ctx.cache[name]["features"]["type"], name])
                # ctx.cache[top_name]["features"] is empty {} dir in case of preproc feature, then we look if there is at least
                # the settings key indicating that this is not a file pattern but a preproc feature
                elif ctx.cache[top_name]["settings"] != {}:
                    name = ctx.cache[top_name]["settings"]["name"]
                    await feature_widget.add_new_feature(["preprocessed_image", name.replace("Setting", "")])

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            if event.worker.name == "cache_file_worker" and self.data_input_success is True:
                self.mount_features()
            if event.worker.name == "feature_worker":
                self.mount_file_panels()
            if event.worker.name == "file_panels_worker":
                self.mount_models()

    @work(exclusive=True, name="file_panels_worker")
    async def mount_file_panels(self):
        # feature_widget = self.app.get_widget_by_id("feature_selection_content")
        feature_widget = self.feature_widget

        for file_object in self.event_file_objects:
            message_dict = {i: [str(file_object.metadata[i])] for i in file_object.metadata}
            for task_based_widget in feature_widget.walk_children(TaskBased):
                # there is no event file panel in PreprocessedOutputOptions
                if type(task_based_widget) is not PreprocessedOutputOptions:
                    widget_name = await task_based_widget.query_one(EventFilePanel).create_file_item(
                        load_object=file_object, message_dict=message_dict
                    )
            ctx.cache[widget_name]["files"] = file_object

        for file_object in self.atlas_file_objects:
            message_dict = {i: [str(file_object.metadata[i])] for i in file_object.metadata}
            for atlas_based_widget in feature_widget.walk_children(AtlasBased):
                widget_name = await atlas_based_widget.query_one(AtlasFilePanel).create_file_item(
                    load_object=file_object, message_dict=message_dict
                )
            ctx.cache[widget_name]["files"] = file_object

        for file_object in self.seed_map_file_objects:
            message_dict = {i: [str(file_object.metadata[i])] for i in file_object.metadata}
            for seed_based_widget in feature_widget.walk_children(SeedBased):
                widget_name = await seed_based_widget.query_one(SeedMapFilePanel).create_file_item(
                    load_object=file_object, message_dict=message_dict
                )
            ctx.cache[widget_name]["files"] = file_object

        for file_object in self.spatial_map_file_objects:
            message_dict = {i: [str(file_object.metadata[i])] for i in file_object.metadata}
            for dual_reg_widget in feature_widget.walk_children(DualReg):
                widget_name = await dual_reg_widget.query_one(SpatialMapFilePanel).create_file_item(
                    load_object=file_object, message_dict=message_dict
                )
            ctx.cache[widget_name]["files"] = file_object

    @work(exclusive=True, name="models_worker")
    async def mount_models(self):
        model_widget = self.model_widget
        if self.existing_spec is not None:
            for model in self.existing_spec.models:
                ctx.cache[model.name]["models"] = copy.deepcopy(model.__dict__)

            # Then create the widgets
            for top_name in ctx.cache:
                if ctx.cache[top_name]["models"] != {}:
                    name = ctx.cache[top_name]["models"]["name"]
                    await model_widget.add_new_model([ctx.cache[name]["models"]["type"], name])
