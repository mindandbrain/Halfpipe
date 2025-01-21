# -*- coding: utf-8 -*-


from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button

from .file_pattern_steps import (
    AddAtlasImageStep,
    AddBinarySeedMapStep,
    AddSpatialMapStep,
    MatEventsStep,
    TsvEventsStep,
    TxtEventsStep,
)
from .non_bids_file_itemization import FileItem
from .selection_modal import SelectionModal


class FilePanelTemplate(Widget):
    """
    FilePanelTemplate class manages a panel of files with interactive features.

    Attributes
    ----------
    file_pattern_counter : int
        Counter to track the number of file patterns.
    class_name : str
        Name of the class.
    id_string : str
        Identifier string for the file panel.
    file_item_id_base : str
        Base ID for file items.
    the_class : type
        Type of the class.
    pattern_class : type
        Pattern class to use for adding file steps.
    current_file_pattern_id : str
        ID of the current file pattern.
    value : reactive[bool]
        Reactive value that monitors the state.

    Methods
    -------
    __init__(id=None, classes=None)
        Initializes the FilePanelTemplate instance with optional id and classes.
    callback_func(message_dict)
        Processes a message dictionary and formats text messages for callback.
    watch_value()
        Posts a message when the value changes.
    compose()
        Yields a vertical scroll widget composition with an add button.
    _on_button_add_file_item_pressed()
        Handles the event when the add file item button is pressed.
    add_file_item_pressed()
        Initiates the creation of a new file item.
    create_file_item(load_object=None, message_dict=None)
        Creates and mounts a new file item widget.
    on_mount()
        Handles actions upon mounting the panel to the application.
    _on_file_item_is_deleted(message)
        Handles the event when a file item is deleted.
    _on_update_all_instances(event)
        Updates instances when a file item is finished or its path pattern changes.
    """

    file_pattern_counter = 0
    class_name = "AtlasFilePanel"
    id_string = "atlas_file_panel"
    file_item_id_base = "atlas_file_pattern_"
    the_class = None
    pattern_class: type | None = AddAtlasImageStep
    current_file_pattern_id = None
    value: reactive[bool] = reactive(None, init=False)

    @dataclass
    class FileItemIsDeleted(Message):
        file_panel: Widget
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_panel

    @dataclass
    class Changed(Message):
        file_panel: Widget
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_panel

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        type(self).the_class = self.__class__  # Sets the_class at the class level
        self.the_app = self.app

    def callback_func(self, message_dict):
        info_string = Text("")
        for key in message_dict:
            if len(message_dict[key]) <= 1:
                sep_char = ""
                separ_line = "-" * (len(key) + len(message_dict[key][0]) + 3)
            else:
                sep_char = "\n"
                separ_line = "-" * (max([len(s) for s in [key] + message_dict[key]]) + 3)
            info_string += Text(key + ": " + sep_char, style="bold green") + Text(
                " ".join(message_dict[key]) + separ_line + "\n", style="white"
            )

        self.callback_message = info_string

    def watch_value(self) -> None:
        self.post_message(self.Changed(self, self.value))

    def compose(self):
        yield VerticalScroll(Button("Add", id="add_file_button"), id=self.id_string)

    @on(Button.Pressed, "#add_file_button")
    async def _on_button_add_file_item_pressed(self):
        await self.add_file_item_pressed()

    async def add_file_item_pressed(self):
        await self.create_file_item(load_object=None)

    async def create_file_item(self, load_object=None, message_dict=None):
        async def mount_file_item_widget():
            if self.the_class is not None and self.pattern_class is not None:
                the_file_item = FileItem(
                    id=self.file_item_id_base + str(self.the_class.file_pattern_counter),
                    classes="file_patterns",
                    pattern_class=self.pattern_class(app=self.app, callback=self.callback_func),
                )
                # regular FileItem mount when user clicks "Add" and creates the file pattern
                await self.get_widget_by_id(self.id_string).mount(the_file_item)
                self.current_file_pattern_id = self.file_item_id_base + str(self.the_class.file_pattern_counter)

                self.the_class.file_pattern_counter += 1
                self.refresh()

        if load_object is None:
            await mount_file_item_widget()
        else:
            # Mounting, for example, when loading the spec file
            if self.the_class is not None:
                # EventFilePanel has pattern_class=None by default, since when user is adding it, he/she is prompt to
                # specify the type. However, if loading from a spec file, we need to determine this by the extension of the
                # item in the spec file
                if self.pattern_class is None:
                    extension_mapping = {".tsv": TsvEventsStep, ".mat": MatEventsStep, ".txt": TxtEventsStep}
                    self.pattern_class = extension_mapping.get(load_object.__dict__["extension"])

                if self.pattern_class is not None:
                    await self.get_widget_by_id(self.id_string).mount(
                        FileItem(
                            id=self.file_item_id_base + str(self.the_class.file_pattern_counter),
                            classes="file_patterns",
                            load_object=load_object,
                            message_dict=message_dict,
                            pattern_class=self.pattern_class(app=self.app, callback=self.callback_func),
                            execute_pattern_class_on_mount=False,
                        )
                    )

                self.current_file_pattern_id = self.file_item_id_base + str(self.the_class.file_pattern_counter)
                self.the_class.file_pattern_counter += 1
        return self.current_file_pattern_id

    def on_mount(self):
        # use first event file panel widget to make copies for the newly created one
        if self.app.walk_children(self.the_class) != []:
            first_file_panel_widget = self.app.walk_children(self.the_class)[0]
            # only use if it is not the first one!
            if first_file_panel_widget != self:
                for file_item_widget in first_file_panel_widget.walk_children(FileItem):
                    # mounting FileItems when a new Feature is added, this basically copies FileItems from the
                    # very first Feature
                    self.get_widget_by_id(self.id_string).mount(
                        FileItem(
                            id=file_item_widget.id,
                            classes="file_patterns",
                            load_object=file_item_widget.get_pattern_match_results,
                            callback_message=file_item_widget.get_callback_message,
                            pattern_class=file_item_widget.get_pattern_class,
                            execute_pattern_class_on_mount=False,
                        )
                    )

    @on(FileItem.IsDeleted)
    async def _on_file_item_is_deleted(self, message):
        message.control.remove()
        self.post_message(self.FileItemIsDeleted(self, message.control.id))

    @on(FileItem.IsFinished)
    @on(FileItem.PathPatternChanged)
    async def _on_update_all_instances(self, event):
        self.value = event.value

    #     # creating copies to all feature tasks
    #     # the one that was is the latest one, create new instances
    #     if event.control.id == self.current_file_pattern_id and event.value["file_pattern"] != "":
    #         # loop through the all existing event file panel
    #         for w in self.app._screen_stacks["_default"][0].walk_children((self.the_class)):
    #             # create new fileitem in every other EventFilePanel
    #             if w != self:
    #                 file_items_ids_in_other_file_panel = [
    #                     other_file_item_widget.id for other_file_item_widget in w.walk_children(FileItem)
    #                 ]
    #                 # id does not exist, mount new FileItem
    #                 if event.control.id not in file_items_ids_in_other_file_panel:
    #                     await w.get_widget_by_id(self.id_string).mount(
    #                         FileItem(
    #                             id=event.control.id,
    #                             classes="file_patterns",
    #                             load_object=event.control.get_pattern_match_results,
    #                             callback_message=event.control.get_callback_message,
    #                         )
    #                     )


class EventFilePanel(FilePanelTemplate):
    """
    EventFilePanel

    A panel to manage event file pattern options, such as SPM, FSL, and BIDS.
    Inherits from FilePanelTemplate.

    Attributes
    ----------
    class_name : str
        Class name identifier.
    id_string : str
        ID string identifier.
    file_item_id_base : str
        Base ID string for file items.
    pattern_class : Class
        Class reference for the pattern type selected.

    Methods
    -------
    add_file_item_pressed(self)
        Handle the action of adding a new file item, prompting the user to
        specify the type of event file and set the corresponding pattern class.
    """

    class_name = "EventFilePanel"
    id_string = "event_file_panel"
    file_item_id_base = "event_file_pattern_"
    pattern_class = None

    async def add_file_item_pressed(self):
        async def proceed_with_choice(choice):
            if choice is not False:
                options_class_map = {"spm": MatEventsStep, "fsl": TxtEventsStep, "bids": TsvEventsStep}
                self.pattern_class = options_class_map[choice]
                await self.create_file_item(load_object=None)

        options = {
            "spm": "SPM multiple conditions",
            "fsl": "FSL 3-column",
            "bids": "BIDS TSV",
        }
        self.app.push_screen(
            SelectionModal(
                title="Event file type specification",
                instructions="Specify the event file type",
                options=options,
                id="event_files_type_modal",
            ),
            proceed_with_choice,
        )


class AtlasFilePanel(FilePanelTemplate):
    """
    A class to represent a panel for handling atlas files, inheriting from FilePanelTemplate.

    Attributes
    ----------
    class_name : str
        Name of the class.
    id_string : str
        Identifier string for the panel.
    file_item_id_base : str
        Base identifier for file items within this panel.
    pattern_class : type
        Class reference associated with the atlas image step functionality.
    """

    class_name = "AtlasFilePanel"
    id_string = "atlas_file_panel"
    file_item_id_base = "atlas_file_pattern_"
    pattern_class = AddAtlasImageStep


class SeedMapFilePanel(FilePanelTemplate):
    """
    A class to represent a panel for handling seed map files, inheriting from FilePanelTemplate.

    Attributes
    ----------
    class_name : str
        Name of the class.
    id_string : str
        Identifier string for the panel.
    file_item_id_base : str
        Base identifier for file items within this panel.
    pattern_class : type
        Class reference associated with the atlas image step functionality.
    """

    class_name = "SeedMapFilePanel"
    id_string = "seed_map_file_panel"
    file_item_id_base = "seed_map_file_pattern_"
    pattern_class = AddBinarySeedMapStep


class SpatialMapFilePanel(FilePanelTemplate):
    """
    A class to represent a panel for handling spatial map files, inheriting from FilePanelTemplate.

    Attributes
    ----------
    class_name : str
        Name of the class.
    id_string : str
        Identifier string for the panel.
    file_item_id_base : str
        Base identifier for file items within this panel.
    pattern_class : type
        Class reference associated with the atlas image step functionality.
    """

    class_name = "SpatialMapFilePanel"
    id_string = "spatial_map_file_panel"
    file_item_id_base = "spatial_map_file_pattern_"
    pattern_class = AddSpatialMapStep
