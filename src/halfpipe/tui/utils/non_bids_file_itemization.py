# -*- coding: utf-8 -*-


from dataclasses import dataclass

from inflection import humanize
from rich.text import Text
from textual import on, work
from textual.containers import Horizontal, HorizontalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerState

from ..utils.confirm_screen import SimpleMessageModal
from ..utils.context import ctx
from ..utils.list_of_files_modal import ListOfFiles
from ..utils.path_pattern_builder import PathPatternBuilder, evaluate_files
from .pattern_suggestor import find_tag_positions_by_color, highlighting


class FileItem(Widget):
    """
    FileItem Class
    Represents a file item widget. It servers to select the file pattern and show the particular found files. Moreover,
    when meta data are present, it shows them.

    Attributes
    ----------
    success_value : reactive[bool]
        Indicator of whether the file pattern match was successful.

    Methods
    -------
    __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
        delete_button=True,
        title="",
        pattern_class=None,
        id_key="",
        load_object=None,
        callback_message=None,
        message_dict=None,
    ) -> None
    Initializes the FileItem widget with optional parameters.

    prettify_message_dict(self, message_dict)
        Converts a dictionary of messages into a styled string format.

    callback_func(self, message_dict)
        Sets the callback message by prettifying the provided message dictionary.

    compose(self)
        Composes UI elements of the FileItem widget.

    on_mount(self) -> None
        Actions to perform when the widget is mounted onto the application.

    _on_edit_button_pressed(self)
        Opens modal for selecting the search file pattern.

    get_pattern_match_results(self)
        Returns the results of the pattern match.

    get_callback_message(self)
        Returns the callback message.

    _update_file_pattern(self, pattern_match_results)
        Updates various variables based on the results from the PathPatternBuilder modal.

    execute_class(self)
        Executes additional pattern class actions if applicable.

    on_worker_state_changed(self, event)
        Handles state changes in the pattern matching worker.

    _on_delete_button_pressed(self)
        Removes the file pattern item.

    _on_show_button_pressed(self)
        Shows a modal with the list of files found using the given pattern.

    _on_info_button_pressed(self)
        Shows a modal with meta information from the callback message.

    remove_all_duplicates(self)
        Removes all duplicate widgets with the same ID.

    update_all_duplicates(self)
        Updates all duplicate widgets with the same ID.
    """

    success_value: reactive[bool] = reactive(None, init=False)

    @dataclass
    class IsDeleted(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class SuccessChanged(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class PathPatternChanged(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class IsFinished(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
        delete_button=True,
        title="",
        pattern_class=None,
        id_key="",
        load_object=None,
        callback_message=None,
        message_dict=None,
        execute_pattern_class_on_mount=True,
    ) -> None:
        """ """
        super().__init__(id=id, classes=classes)
        self.delete_button = delete_button
        self.pattern_class = None if pattern_class is None else pattern_class
        self.title = "Not implemented yet"
        if self.pattern_class is not None:
            self.title = self.pattern_class.header_str
            if self.pattern_class.next_step_type is not None:
                self.pattern_class.callback = self.callback_func
            self.pattern_class.id_key = id

        self.load_object = load_object
        self.border_title = "id: " + str(id)
        self.from_edit = False
        if message_dict is not None and callback_message is None:
            self.callback_message = self.prettify_message_dict(message_dict)
        else:
            self.callback_message = callback_message

        self.pattern_match_results = {"file_pattern": "", "message": "Found 0 files.", "files": []}
        self.execute_pattern_class_on_mount = execute_pattern_class_on_mount

    def prettify_message_dict(self, message_dict):
        info_string = Text("")
        for key in message_dict:
            # if there is only one item, we do not separate items on new lines
            if len(message_dict[key]) <= 1:
                sep_char = ""
                separ_line = "-" * (len(key) + len(message_dict[key]) + 3)
            else:
                sep_char = "\n"
                separ_line = "-" * (max([len(s) for s in [key] + message_dict[key]]) + 3)
            message_value = ""
            for message in message_dict[key]:
                message_value += message + " " if message.endswith("\n") else message + "\n"
            info_string += Text(humanize(key) + ": " + sep_char, style="bold green") + Text(
                message_value + separ_line, style="white"
            )
        return info_string

    def callback_func(self, message_dict):
        self.callback_message = self.prettify_message_dict(message_dict)

    def compose(self):
        yield HorizontalScroll(Static("Edit to enter the file pattern", id="static_file_pattern"))
        with Horizontal(id="icon_buttons_container"):
            yield Button(" ℹ", id="info_button", classes="icon_buttons")

            yield Button("🖌", id="edit_button", classes="icon_buttons")
            yield Button("👁", id="show_button", classes="icon_buttons")
            if self.delete_button:
                yield Button("❌", id="delete_button", classes="icon_buttons")

    def on_mount(self) -> None:
        if self.load_object is None:
            self.get_widget_by_id("edit_button").tooltip = "Edit"
            if self.delete_button:
                self.get_widget_by_id("delete_button").tooltip = "Delete"
            if self.pattern_class is not None:
                self.app.push_screen(
                    PathPatternBuilder(
                        path="/home/tomas/github/ds005115/sub-01/ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz",
                        title=self.title,
                        highlight_colors=self.pattern_class.get_entity_colors_list,
                        labels=self.pattern_class.get_entities,
                        pattern_class=self.pattern_class,
                    ),
                    self._update_file_pattern,
                )
        else:
            if isinstance(self.load_object, dict):
                self._update_file_pattern(self.load_object)
            else:
                pattern_load = {}
                pattern_load["file_pattern"] = self.load_object.path
                message, filepaths = evaluate_files(self.load_object.path)
                pattern_load["message"] = message
                pattern_load["files"] = filepaths
                self._update_file_pattern(pattern_load)
        if (self.pattern_class and self.pattern_class.callback) or self.callback_message:
            self.get_widget_by_id("info_button").styles.visibility = "visible"
        else:
            self.get_widget_by_id("info_button").remove()

    @on(Button.Pressed, "#edit_button")
    def _on_edit_button_pressed(self):
        """
        Opens modal for selecting the search file pattern.
        The results from this modal goes then to _update_file_pattern function.
        """
        self.from_edit = True
        if self.pattern_class is not None:
            self.app.push_screen(
                PathPatternBuilder(
                    path=self.pattern_match_results["file_pattern"],
                    title=self.title,
                    highlight_colors=self.pattern_class.get_entity_colors_list,
                    labels=self.pattern_class.get_entities,
                    pattern_class=self.pattern_class,
                ),
                self._update_file_pattern,
            )

    @property
    def get_pattern_match_results(self):
        return self.pattern_match_results

    @property
    def get_callback_message(self):
        return self.callback_message

    @property
    def get_pattern_class(self):
        return self.pattern_class

    # runs after the PathPatternBuilder modal
    @work(exclusive=True, name="update_worker")
    async def _update_file_pattern(self, pattern_match_results):
        """Update various variables based on the results from the PathPatternBuilder"""
        if pattern_match_results is not False:
            self.pattern_match_results = pattern_match_results
            # Update the static label using the file pattern.

            if self.pattern_class is not None:
                colors_and_labels = dict(
                    zip(self.pattern_class.get_entity_colors_list, self.pattern_class.get_entities, strict=False)
                )
                current_highlights = find_tag_positions_by_color(pattern_match_results["file_pattern"], colors_and_labels)
            else:
                current_highlights = []

            # ensure that this is a string before wrapping it as rich Text
            pattern_match_results["file_pattern"] = (
                pattern_match_results["file_pattern"].plain
                if isinstance(pattern_match_results["file_pattern"], Text)
                else pattern_match_results["file_pattern"]
            )
            self.get_widget_by_id("static_file_pattern").update(
                highlighting(Text(pattern_match_results["file_pattern"]), current_highlights)
            )
            # self.get_widget_by_id("static_file_pattern").update(pattern_match_results["file_pattern"])
            # Tooltip telling us how many files were  found.
            self.get_widget_by_id("show_button").tooltip = pattern_match_results["message"]
            # If 0 files were found, the border is red, otherwise green.
            if len(pattern_match_results["files"]) > 0:
                self.styles.border = ("solid", "green")
                self.success_value = True
            else:
                self.styles.border = ("solid", "red")
                self.success_value = False
            if len(pattern_match_results["files"]) > 0:
                if self.pattern_class is not None and self.execute_pattern_class_on_mount:
                    await self.execute_class()

            if self.from_edit:
                await self.update_all_duplicates()

        else:
            # delete it self if cancelled and was not existing before
            if self.pattern_match_results["file_pattern"] == "":
                self.remove_all_duplicates()
                self.remove()

    async def execute_class(self):
        if self.pattern_class is not None:
            # fix this because sometimes this can be just ordinary string
            if isinstance(self.pattern_match_results["file_pattern"], str):
                await self.pattern_class.push_path_to_context_obj(path=self.pattern_match_results["file_pattern"])
            elif isinstance(self.pattern_match_results["file_pattern"], Text):
                await self.pattern_class.push_path_to_context_obj(path=self.pattern_match_results["file_pattern"].plain)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "update_worker":
            if event.state == WorkerState.SUCCESS:
                self.pattern_match_results["callback_message"] = self.get_callback_message
                self.post_message(self.PathPatternChanged(self, self.pattern_match_results))

    @on(Button.Pressed, "#delete_button")
    def _on_delete_button_pressed(self):
        """Remove the file pattern item."""
        # Creation of the FileItem does not automatically imply creation in the cache.
        # For this a pattern needs to be created. By cancelling the modal, the widget is created but the filepattern is not.
        if self.id in ctx.cache:
            ctx.cache.pop(self.id)
        self.remove_all_duplicates()
        self.post_message(self.IsDeleted(self, "yes"))

    @on(Button.Pressed, "#show_button")
    def _on_show_button_pressed(self):
        """Shows a modal with the list of files found using the given pattern."""
        self.app.push_screen(ListOfFiles(self.pattern_match_results))

    @on(Button.Pressed, "#info_button")
    def _on_info_button_pressed(self):
        """Shows a modal with the list of files found using the given pattern."""
        self.app.push_screen(SimpleMessageModal(self.callback_message, title="Meta information"))

    def remove_all_duplicates(self):
        for w in self.app.walk_children(FileItem):
            # remove itself standardly later
            if w.id == self.id and w != self:
                w.remove()

    async def update_all_duplicates(self):
        for w in self.app.walk_children(FileItem):
            # remove itself standardly later
            if w.id == self.id and w != self:
                if w.pattern_match_results != self.pattern_match_results:
                    await w._update_file_pattern(self.pattern_match_results)
        self.from_edit = False
