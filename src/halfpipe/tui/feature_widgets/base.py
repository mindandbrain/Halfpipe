# -*- coding: utf-8 -*-
# ok to review

import copy

import numpy as np
from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, Input, Label, ListItem, ListView, OptionList, Placeholder
from textual.widgets.option_list import Option, Separator

from ..utils.confirm_screen import Confirm
from ..utils.context import ctx
from ..utils.draggable_modal_screen import DraggableModalScreen
from .features import AtlasBased, DualReg, Falff, PreprocessedOutputOptions, ReHo, SeedBased, TaskBased

FEATURES_MAP = {
    "task_based": "Task-based",
    "seed_based_connectivity": "Seed-based connectivity",
    "dual_regression": "Dual regression",
    "atlas_based_connectivity": "Atlas-based connectivity matrix",
    "reho": "ReHo",
    "falff": "fALFF",
    "preprocessed_image": "Output preprocessed image",
}

FEATURES_MAP_colors = {
    "task_based": "crimson",
    "seed_based_connectivity": "silver",
    "dual_regression": "ansi_bright_cyan",
    "atlas_based_connectivity": "blueviolet",
    "reho": "slategray",
    "falff": "magenta",
    "preprocessed_image": "white",
}


class FeatureNameInput(DraggableModalScreen):
    """
    FeatureNameInput Class for a Draggable Modal Screen input interface.

    Attributes
    ----------
    CSS_PATH : list
        The CSS paths used by the class.

    Methods
    -------
    __init__(occupied_feature_names)
        Initializes the FeatureNameInput class with occupied feature names.

    on_mount()
        Mounts the input field and buttons on the modal screen when it is created.

    ok()
        Handles the 'Ok' button press event.

    cancel()
        Handles the 'Cancel' button press event.

    key_escape()
        Handles escape key press to cancel the modal.

    _confirm_window()
        Confirms the input feature name and performs validation checks.

    _cancel_window()
        Closes the modal window without confirmation.
    """

    CSS_PATH = ["tcss/feature_name_input.tcss"]

    def __init__(self, occupied_feature_names) -> None:
        #   self.top_parent = top_parent
        self.occupied_feature_names = occupied_feature_names
        super().__init__()
        self.title_bar.title = "Feature name"

    def on_mount(self) -> None:
        self.content.mount(
            Input(
                placeholder="Enter feature name",
                id="feature_name",
                classes="feature_name",
            ),
            Horizontal(
                Button("Ok", id="ok", classes="button"),
                Button("Cancel", id="cancel", classes="button"),
                classes="button_grid",
            ),
        )

    @on(Button.Pressed, "#ok")
    def ok(self):
        self._confirm_window()

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self._cancel_window()

    def key_escape(self):
        self._cancel_window()

    def _confirm_window(self):
        feature_name = self.get_widget_by_id("feature_name").value
        if feature_name == "":
            self.app.push_screen(
                Confirm(
                    "Enter a name!",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Missing name",
                    classes="confirm_error",
                )
            )

        elif feature_name in self.occupied_feature_names:
            self.app.push_screen(
                Confirm(
                    "Name already exists!\nUse another one.",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Existing name",
                    classes="confirm_error",
                )
            )
        else:
            self.dismiss(feature_name)

    def _cancel_window(self):
        self.dismiss(None)


class FeatureSelectionScreen(DraggableModalScreen):
    """
    FeatureSelectionScreen
    ----------------------
    A class to create a draggable modal screen for selecting features. It extends from DraggableModalScreen and is used to
    present a list of features from which the first level feature can be chosen.

    Attributes
    ----------
    CSS_PATH : str
        The path to the CSS stylesheet used for this screen.
    occupied_feature_names : list
        List of feature names that are already occupied.
    option_list : OptionList
        An option list to display the available feature choices.
    title_bar : TitleBar
        The title bar displaying the title of the screen.

    Methods
    -------
    __init__(occupied_feature_names) -> None
        Initializes the FeatureSelectionScreen with occupied feature names and sets up the option list.
    on_mount() -> None
        Mounts the option list and the Cancel button to the screen.
    on_option_list_option_selected(message: OptionList.OptionSelected) -> None
        Handles the event where an option from the option list is selected, prompting the user to input a feature name.
    key_escape(self)
        Handles the escape action when the Cancel button is pressed, dismissing the screen without making a selection.
    """

    CSS_PATH = "tcss/feature_selection_screen.tcss"

    def __init__(self, occupied_feature_names) -> None:
        #    self.top_parent = top_parent
        self.occupied_feature_names = occupied_feature_names
        super().__init__()
        # Temporary workaround because some bug in Textual between versions 0.70 and 0.75.
        self.option_list = OptionList(
            Option(FEATURES_MAP["task_based"], id="task_based"),
            Separator(),
            Option(FEATURES_MAP["seed_based_connectivity"], id="seed_based_connectivity"),
            Separator(),
            Option(FEATURES_MAP["dual_regression"], id="dual_regression"),
            Separator(),
            Option(FEATURES_MAP["atlas_based_connectivity"], id="atlas_based_connectivity"),
            Separator(),
            Option(FEATURES_MAP["reho"], id="reho"),
            Separator(),
            Option(FEATURES_MAP["falff"], id="falff"),
            Separator(),
            Option(FEATURES_MAP["preprocessed_image"], id="preprocessed_image"),
            Separator(),
            id="options",
        )
        # self.option_list = OptionList(id="options")
        # for f in FEATURES_MAP:
        #     # option_list = self.get_widget_by_id("options")
        #     self.option_list.add_option(Option(FEATURES_MAP[f], id=f))
        #     self.option_list.add_option(Separator())

        self.title_bar.title = "Choose first level feature"

    def on_mount(self) -> None:
        self.content.mount(self.option_list, Horizontal(Button("Cancel", id="cancel_button"), id="botton_container"))

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        def get_feature_name(feature_name: str | None) -> None:
            if feature_name is not None:
                self.dismiss((message.option.id, feature_name))

        self.app.push_screen(
            FeatureNameInput(self.occupied_feature_names),
            get_feature_name,
        )

    @on(Button.Pressed, "#cancel_button")
    def key_escape(self):
        self.dismiss(False)


class FeatureItem:
    """
    FeatureItem class to represent a feature with a type and name.

    Attributes
    ----------
    type : str
        The type of the feature.
    name : str
        The name of the feature.
    """

    def __init__(self, _type, name):
        self.type = _type
        self.name = name


class SelectionTemplate(Widget):
    BINDINGS = [("a", "add_item", "Add"), ("d", "delete_feature", "Delete")]
    current_order = ["name", "type"]

    def __init__(self, disabled=False, **kwargs) -> None:
        """Each created widget needs to have a unique id, even after deletion it cannot be recycled.
        The id_counter takes care of this and feature_items dictionary keeps track of the id number and feature name.
        """
        super().__init__(disabled=disabled, **kwargs)
        # self.top_parent = app
        #   self.ctx = ctx
        # self.available_images = available_images
        #    ctx.cache = user_selections_dict
        self._id_counter = 0
        self.feature_items: dict = {}

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Grid(
                Button("New", variant="primary", classes="add_button"),
                Button("Rename", variant="primary", classes="rename_button"),
                Button("Duplicate", variant="primary", classes="duplicate_button"),
                Button("Delete", variant="primary", classes="delete_button"),
                Button("Sort", variant="primary", classes="sort_button"),
                classes="buttons",
            ),
            ListView(id="list", classes="list"),
            id="sidebar",
        )
        #  yield EventFilePanel()
        yield ContentSwitcher(id="content_switcher")

    @on(Button.Pressed, "#sidebar .add_button")
    async def add(self) -> None:
        await self.run_action("add_item")

    @on(Button.Pressed, "#sidebar .delete_button")
    async def delete(self) -> None:
        await self.run_action("delete_feature")

    @on(Button.Pressed, "#sidebar .duplicate_button")
    async def duplicate(self) -> None:
        await self.run_action("duplicate_feature")

    @on(Button.Pressed, "#sidebar .sort_button")
    async def sort(self) -> None:
        await self.run_action("sort_features")

    def action_delete_feature(self) -> None:
        """Unmount the feature and delete its entry from dictionaries."""

        def confirmation(respond: bool):
            if respond:
                current_id = self.get_widget_by_id("content_switcher").current
                name = self.feature_items[current_id].name
                self.get_widget_by_id(current_id).remove()
                self.feature_items.pop(current_id)
                ctx.cache.pop(name)

        self.app.push_screen(Confirm(), confirmation)

    def action_sort_features(self):
        """Sorting alphabetically and by feature type."""

        def sort_children(by):
            for i in range(len(self.feature_items.keys())):
                current_list_item_ids = [i.id for i in self.get_widget_by_id("list").children]
                item_names = [getattr(self.feature_items[i], by) for i in current_list_item_ids]
                correct_order = np.argsort(np.argsort(item_names))
                which_to_move = list(correct_order).index(np.int64(i))
                self.get_widget_by_id("list").move_child(int(which_to_move), before=int(i))

        sort_children(self.current_order[0])
        sort_children(self.current_order[1])
        self.current_order = [self.current_order[1], self.current_order[0]]


class FeatureSelection(SelectionTemplate):
    """
    FeatureSelection(Widget)
    A widget for feature selection, allowing users to add, rename, duplicate, delete, and sort features.

    Attributes
    ----------
    BINDINGS : list
        A list of binding tuples for feature actions.
    current_order : list
        A list defining the default order of features.

    Methods
    -------
    __init__(self, disabled=False, **kwargs) -> None
        Each created widget needs to have a unique id, even after deletion it cannot be recycled.
        The id_counter takes care of this and feature_items dictionary keeps track of the id number and feature name.

    compose(self) -> ComposeResult
        Generates the layout of the widget, including the sidebar with buttons and a content switcher.

    on_mount(self) -> None
        Sets the initial border title of the content switcher to "First-level features".

    on_list_view_selected(self, event: ListView.Selected) -> None
        Changes border title color according to the feature type.

    add(self) -> None
        Binds the "Add" button to the add_item action.

    delete(self) -> None
        Binds the "Delete" button to the delete_feature action.

    rename(self) -> None
        Pops up a screen to set the new feature name. Afterwards the dictionary entry is also renamed.

    duplicate(self) -> None
        Binds the "Duplicate" button to the duplicate_feature action.

    sort(self) -> None
        Binds the "Sort" button to the sort_features action.

    action_add_item(self) -> None
        Pops out the feature type selection windows and then uses add_new_feature function to mount a new feature widget.

    add_new_feature(self, new_feature_item: tuple | bool) -> None
        Adds a new feature by mounting a new widget and creating a new entry in the dictionary to keep track of selections.

    action_delete_feature(self) -> None
        Unmount the feature and delete its entry from dictionaries.

    action_duplicate_feature(self)
        Duplicates the feature by a deep copy of the dictionary entry and then mounts a new widget while loading defaults from
        this copy.
    """

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Changes border title color according to the feature type."""
        current_id = event.item.id
        current_feature = self.feature_items[current_id]
        self.get_widget_by_id("content_switcher").current = current_id
        self.get_widget_by_id("content_switcher").border_title = "{}: {}".format(
            FEATURES_MAP[current_feature.type], current_feature.name
        )
        self.get_widget_by_id("content_switcher").styles.border_title_color = FEATURES_MAP_colors[current_feature.type]

    def on_mount(self) -> None:
        self.get_widget_by_id("content_switcher").border_title = "First-level features"

    @on(Button.Pressed, "#sidebar .rename_button")
    async def rename(self) -> None:
        """Pops up a screen to set the new feature name. Afterwards the dictionary entry is also renamed."""

        def action_rename_feature(new_feature_name: str) -> None:
            if new_feature_name is not None:
                currently_selected_id = self.get_widget_by_id("content_switcher").current
                old_feature_name = self.feature_items[currently_selected_id].name

                self.feature_items[currently_selected_id].name = new_feature_name
                self.query_one("#" + currently_selected_id + " .labels").update(new_feature_name)
                self.get_widget_by_id("content_switcher").border_title = "{}: {}".format(
                    FEATURES_MAP[self.feature_items[currently_selected_id].type],
                    old_feature_name,
                )
                ctx.cache[new_feature_name] = ctx.cache.pop(old_feature_name)
                ctx.cache[new_feature_name]["features"]["name"] = new_feature_name
                ctx.cache[new_feature_name]["features"]["setting"] = new_feature_name + "Setting"
                ctx.cache[new_feature_name]["settings"]["name"] = new_feature_name + "Setting"

        occupied_feature_names = [self.feature_items[item].name for item in self.feature_items]
        await self.app.push_screen(
            FeatureNameInput(occupied_feature_names),
            action_rename_feature,
        )

    def action_add_item(self) -> None:
        # Try here first the event files
        # setting_filter_step_instance = SettingFilterStep()
        # setting_filter_step_instance.run()
        #  events_type_instance = EventsTypeStep()
        #  events_type_instance.run()

        """Pops out the feature type selection windows and then uses add_new_feature function to mount a new feature
        widget."""
        occupied_feature_names = [self.feature_items[item].name for item in self.feature_items]
        self.app.push_screen(
            FeatureSelectionScreen(occupied_feature_names),
            self.add_new_feature,
        )

    async def add_new_feature(self, new_feature_item: tuple | bool) -> None:
        """Principle of adding a new feature lies in mounting a new widget while creating a new entry in the dictionary
        to keep track of the selections which are later dumped into the Context object.
        If this is a load or a duplication, then new entry is not created but read from the dictionary.
        The dictionary entry was created elsewhere.
        """
        # print("new_feature_itemnew_feature_itemnew_feature_itemnew_feature_item", new_feature_item)
        if isinstance(new_feature_item, tuple) or isinstance(new_feature_item, list):
            feature_type, feature_name = new_feature_item
            new_id = "feature_item_" + str(self._id_counter)
            self.feature_items[new_id] = FeatureItem(feature_type, feature_name)
            # the pseudo class here is to set a particular text color in the left panel
            new_list_item = ListItem(
                Label(feature_name, id=new_id, classes="labels " + feature_type),
                id=new_id,
                classes="items",
            )
            # this dictionary will contain all made choices
            if feature_name not in ctx.cache:
                if feature_type != "preprocessed_image":
                    ctx.cache[feature_name]["features"]["name"] = feature_name
                    ctx.cache[feature_name]["features"]["setting"] = feature_name + "Setting"
                    ctx.cache[feature_name]["settings"]["name"] = feature_name + "Setting"
                else:
                    ctx.cache[feature_name]["settings"]["name"] = feature_name + "UnfilteredSetting"
                    ctx.cache[feature_name]["settings"]["output_image"] = True
            feature_type_class: type
            if feature_type == "task_based":
                feature_type_class = TaskBased
            elif feature_type == "seed_based_connectivity":
                feature_type_class = SeedBased
            elif feature_type == "dual_regression":
                feature_type_class = DualReg
            elif feature_type == "atlas_based_connectivity":
                feature_type_class = AtlasBased
            elif feature_type == "preprocessed_image":
                feature_type_class = PreprocessedOutputOptions
            elif feature_type == "reho":
                feature_type_class = ReHo
            elif feature_type == "falff":
                feature_type_class = Falff
            if feature_type_class is not None:
                new_content_item = feature_type_class(
                    this_user_selection_dict=ctx.cache[feature_name],
                    id=new_id,
                    classes="feature",
                )
            else:
                new_content_item = Placeholder(str(self._id_counter), id=new_id, classes=feature_type)
            await self.get_widget_by_id("list").mount(new_list_item)
            await self.get_widget_by_id("content_switcher").mount(new_content_item)
            self.get_widget_by_id("content_switcher").current = new_id
            self.get_widget_by_id("content_switcher").border_title = "{}: {}".format(
                FEATURES_MAP[self.feature_items[new_id].type],
                self.feature_items[new_id].name,
            )
            self.get_widget_by_id("content_switcher").styles.border_title_color = FEATURES_MAP_colors[feature_type]
            self._id_counter += 1

    async def action_duplicate_feature(self):
        """Duplicating feature by a deep copy of the dictionary entry and then mounting a new widget while
        loading defaults from this copy.
        """
        current_id = self.get_widget_by_id("content_switcher").current
        feature_name = self.feature_items[current_id].name
        feature_name_copy = feature_name + "Copy"
        ctx.cache[feature_name_copy] = copy.deepcopy(ctx.cache[feature_name])
        ctx.cache[feature_name_copy]["features"]["name"] = feature_name_copy
        ctx.cache[feature_name_copy]["features"]["setting"] = feature_name_copy + "Setting"
        ctx.cache[feature_name_copy]["settings"]["name"] = feature_name_copy + "Setting"
        await self.add_new_feature((ctx.cache[feature_name_copy]["features"]["type"], feature_name_copy))
