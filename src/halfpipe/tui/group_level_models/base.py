# -*- coding: utf-8 -*-


import copy

from textual import on
from textual.containers import Horizontal
from textual.widgets import Button, Label, ListItem, ListView, OptionList
from textual.widgets.option_list import Option, Separator

from ..feature_widgets.base import FeatureNameInput, SelectionTemplate
from ..utils.context import ctx
from ..utils.draggable_modal_screen import DraggableModalScreen
from .models import InterceptOnlyModel, LinearModel

MODELS_MAP = {"me": "Intercept-only", "lme": "Linear model"}

MODELS_MAP_colors = {
    "me": "crimson",
    "lme": "blueviolet",
}


class GroupLevelModelSelectionScreen(DraggableModalScreen):
    """
    modelSelectionScreen
    ----------------------
    A class to create a draggable modal screen for selecting models. It extends from DraggableModalScreen and is used to
    present a list of models from which the first level model can be chosen.

    Attributes
    ----------
    CSS_PATH : str
        The path to the CSS stylesheet used for this screen.
    occupied_model_names : list
        List of model names that are already occupied.
    option_list : OptionList
        An option list to display the available model choices.
    title_bar : TitleBar
        The title bar displaying the title of the screen.

    Methods
    -------
    __init__(occupied_model_names) -> None
        Initializes the modelSelectionScreen with occupied model names and sets up the option list.
    on_mount() -> None
        Mounts the option list and the Cancel button to the screen.
    on_option_list_option_selected(message: OptionList.OptionSelected) -> None
        Handles the event where an option from the option list is selected, prompting the user to input a model name.
    key_escape(self)
        Handles the escape action when the Cancel button is pressed, dismissing the screen without making a selection.
    """

    CSS_PATH = "tcss/group_level_selection_screen.tcss"

    def __init__(self, occupied_names) -> None:
        #    self.top_parent = top_parent
        self.occupied_names = occupied_names
        super().__init__()
        # Temporary workaround because some bug in Textual between versions 0.70 and 0.75.
        self.option_list = OptionList(
            Separator(),
            Option("Intercept only", id="me"),
            Separator(),
            Option("Linear model", id="lme"),
            Separator(),
            id="options",
        )

        self.title_bar.title = "Specify model type"

    def on_mount(self) -> None:
        self.content.mount(self.option_list, Horizontal(Button("Cancel", id="cancel_button"), id="botton_container"))

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        def get_selection_name(selection_name: str | None) -> None:
            if selection_name is not None:
                self.dismiss((message.option.id, selection_name))

        self.app.push_screen(
            FeatureNameInput(self.occupied_names),
            get_selection_name,
        )

    @on(Button.Pressed, "#cancel_button")
    def key_escape(self):
        self.dismiss(False)


class ModelItem:
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


class GroupLevelModelSelection(SelectionTemplate):
    """This is for group level models"""

    def on_mount(self) -> None:
        self.get_widget_by_id("content_switcher").border_title = "Group-level models"

    def action_add_item(self) -> None:
        # Try here first the event files
        # setting_filter_step_instance = SettingFilterStep()
        # setting_filter_step_instance.run()
        #  events_type_instance = EventsTypeStep()
        #  events_type_instance.run()

        """Pops out the model type selection windows and then uses add_new_model function to mount a new model
        widget."""
        occupied_model_names = [self.feature_items[item].name for item in self.feature_items]
        self.app.push_screen(
            GroupLevelModelSelectionScreen(occupied_model_names),
            self.add_new_model,
        )

    async def add_new_model(self, new_model_item: tuple | bool) -> None:
        """Principle of adding a new model lies in mounting a new widget while creating a new entry in the dictionary
        to keep track of the selections which are later dumped into the Context object.
        If this is a load or a duplication, then new entry is not created but read from the dictionary.
        The dictionary entry was created elsewhere.
        """
        # print("new_model_itemnew_model_itemnew_model_itemnew_model_item", new_model_item)
        if isinstance(new_model_item, tuple) or isinstance(new_model_item, list):
            model_type, model_name = new_model_item
            new_id = "model_item_" + str(self._id_counter)
            self.feature_items[new_id] = ModelItem(model_type, model_name)
            # the pseudo class here is to set a particular text color in the left panel
            new_list_item = ListItem(
                Label(model_name, id=new_id, classes="labels " + model_type),
                id=new_id,
                classes="items",
            )
            # this dictionary will contain all made choices
            if model_name not in ctx.cache:
                ctx.cache[model_name]["models"]["name"] = model_name

            model_type_class: type
            if model_type == "me":
                model_type_class = InterceptOnlyModel
            elif model_type == "lme":
                model_type_class = LinearModel
            if model_type_class is not None:
                new_content_item = model_type_class(
                    this_user_selection_dict=ctx.cache[model_name],
                    id=new_id,
                    classes="model",
                )

            await self.get_widget_by_id("list").mount(new_list_item)
            await self.get_widget_by_id("content_switcher").mount(new_content_item)
            self.get_widget_by_id("content_switcher").current = new_id
            self.get_widget_by_id("content_switcher").border_title = "{}: {}".format(
                MODELS_MAP[self.feature_items[new_id].type],
                self.feature_items[new_id].name,
            )
            self.get_widget_by_id("content_switcher").styles.border_title_color = MODELS_MAP_colors[model_type]
            self._id_counter += 1

    @on(Button.Pressed, "#sidebar .duplicate_button")
    async def duplicate(self) -> None:
        await self.run_action("duplicate_model")

    async def action_duplicate_model(self):
        """Duplicating feature by a deep copy of the dictionary entry and then mounting a new widget while
        loading defaults from this copy.
        """
        current_id = self.get_widget_by_id("content_switcher").current
        model_name = self.feature_items[current_id].name
        model_name_copy = model_name + "Copy"
        ctx.cache[model_name_copy] = copy.deepcopy(ctx.cache[model_name])
        ctx.cache[model_name_copy]["models"]["name"] = model_name_copy
        await self.add_new_model((ctx.cache[model_name_copy]["models"]["type"], model_name_copy))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Changes border title color according to the feature type."""
        current_id = event.item.id
        current_feature = self.feature_items[current_id]
        self.get_widget_by_id("content_switcher").current = current_id
        self.get_widget_by_id("content_switcher").border_title = "{}: {}".format(
            MODELS_MAP[current_feature.type], current_feature.name
        )
        self.get_widget_by_id("content_switcher").styles.border_title_color = MODELS_MAP_colors[current_feature.type]
