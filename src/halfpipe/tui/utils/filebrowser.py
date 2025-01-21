# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from ...model.file.bids import BidsFileSchema
from .context import ctx
from .file_browser_modal import FileBrowserModal


class FileBrowser(Widget):
    """
    FileBrowser is a widget class for browsing files within a UI.

    Attributes
    ----------
    DEFAULT_CSS : str
        The default CSS styling for FileBrowser.
    selected_path : reactive[str]
        Reactive property to store the selected file path.

    Methods
    -------
    watch_selected_path():
        Watches for changes to the selected_path attribute and posts a message when it changes.
    __init__(path_to="", modal_title="Browse", id: str | None = None, classes: str | None = None, **kwargs):
        Initializes the FileBrowser widget with the specified path, title, ID, and CSS classes.
    compose() -> ComposeResult:
        Composes the internal layout of the FileBrowser widget.
    on_button_pressed():
        Handles the event when the browse button is pressed.
    open_browse_window():
        Opens the file browsing modal window.
    update_from_input():
        Updates the selected path based on user input from the input box.
    update_input(selected_path: str):
        Updates the internal state and UI with the selected path.
    """

    DEFAULT_CSS = """
    FileBrowser {
        border: tall transparent;
        background: $boost;
        height: auto;
        width: auto;
        padding: 0 2;
    }
    """

    selected_path: reactive[str] = reactive("", init=False)

    @dataclass
    class Changed(Message):
        file_browser: "FileBrowser"
        selected_path: str

        @property
        def control(self):
            return self.file_browser

    def watch_selected_path(self) -> None:
        self.post_message(self.Changed(self, self.selected_path))

    def __init__(self, path_to="", modal_title="Browse", id: str | None = None, classes: str | None = None, **kwargs) -> None:
        super().__init__(id=id, classes=classes)
        self.path_to = path_to
        self.modal_title = modal_title

    def compose(self) -> ComposeResult:
        with Horizontal(id="file_browser"):
            yield Button("Browse", id="file_browser_edit_button", classes="button")
            yield Label(self.path_to + ":", id="path_input_box")

    @on(Button.Pressed, "#file_browser_edit_button")
    def on_button_pressed(self):
        self.open_browse_window()

    def open_browse_window(self):
        self.app.push_screen(FileBrowserModal(title=self.modal_title), self.update_input)

    @on(Input.Submitted, "#path_input_box")
    def update_from_input(self):
        self.update_input(self.get_widget_by_id("path_input_box").value)

    def update_input(self, selected_path: str) -> None:
        if selected_path != "" and selected_path is not False:
            label = self.get_widget_by_id("path_input_box")
            label.update(self.path_to + ": " + str(selected_path))
            label.value = self.path_to + ": " + str(selected_path)
            self.selected_path = str(selected_path)


def path_test_for_bids(path, isfile=False):
    """
    Except for testing whether a correct type was selected (folder) or whether the user has permissions for the directory,
    the function tests whether the folder contains a bids database by loading the directory and checking for bold files.
    Parameters
    ----------
    path : str
        The path to be tested.
    isfile : bool, optional
        Flag indicating whether the specified path should be a file (True) or a directory (False). Default is False.

    Returns
    -------
    str
        A string describing the result of the path validation, including potential errors or success messages.
    """
    if os.path.exists(path):
        if os.access(path, os.W_OK):
            if isfile:
                result_info = "OK" if os.path.isfile(path) else "A directory was selected instead of a file!"
            else:
                result_info = "OK" if os.path.isdir(path) else "A file was selected instead of a directory!"
        else:
            result_info = "Permission denied."
    else:
        result_info = "File not found."
    if result_info == "OK":
        bold_filedict = {"datatype": "func", "suffix": "bold"}
        ctx.put(BidsFileSchema().load({"datatype": "bids", "path": path}))
        ctx.refresh_available_images()

        if len(list(ctx.database.get(**bold_filedict))) == 0:
            result_info = "The selected data directory seems not be a BIDS directory! No BOLD files found!"
            ctx.spec.files.pop()
    return result_info


class FileBrowserForBIDS(FileBrowser):
    """
    FileBrowserForBIDS
    A specialized file browser class for BIDS-compatible file selection.

    Methods
    -------
    open_browse_window()
        Opens a file browsing window with a modality filter for BIDS-compatible paths.
    """

    def open_browse_window(self):
        self.app.push_screen(
            FileBrowserModal(title=self.modal_title, path_test_function=path_test_for_bids), self.update_input
        )
