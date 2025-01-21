# -*- coding: utf-8 -*-

import re

from rich.text import Text
from textual import events, on
from textual.containers import Container, Grid, HorizontalScroll
from textual.widgets import Button, Static

from .confirm_screen import Confirm
from .draggable_modal_screen import DraggableModalScreen
from .file_browser_modal import FileBrowserModal, path_test_with_isfile_true
from .list_of_files_modal import ListOfFiles
from .pattern_suggestor import (
    InputWithColoredSuggestions,
    SegmentHighlighting,
    SelectCurrentWithInputAndSegmentHighlighting,
)


# utilities
def convert_validation_error_to_string(error):
    # `error.messages` contains the validation errors as a dictionary
    result = []

    for field, messages in error.messages.items():
        # Join the list of error messages for each field into a single string
        messages_str = ", ".join(messages)
        result.append(f"{field}: {messages_str}")

    # Return all error messages concatenated into a single string, separated by '; '
    return "; ".join(result)


def check_wrapped_tags(path, tags):
    # Regular expression to check for keywords wrapped in curly braces
    pattern = r"\{(" + "|".join(tags) + r")\}"

    # Search for the pattern in the input string
    match = re.search(pattern, path)

    # Return True if a match is found, otherwise False
    return bool(match)


def evaluate_files(newpathname):
    """
    Function to evaluate how many and what files were found based on the provided file pattern.
    TODO: refine the whole function
    """
    from os import path as op
    from threading import Event

    import inflect

    from ...ingest.glob import (
        suggestion_match,
        tag_glob,
    )

    class Config:
        fs_root: str = "/"

    def resolve(path) -> str:
        abspath = op.abspath(path)

        fs_root = Config.fs_root

        if not abspath.startswith(fs_root):
            abspath = fs_root + abspath

        return op.normpath(abspath)

    # all possible entities
    schema_entities = ["subject", "session", "run", "acquisition", "task", "atlas", "seed", "map", "desc"]
    dironly = False

    # empty string gives strange behaviour!
    newpathname = newpathname if newpathname != "" else "/"
    tag_glob_generator = tag_glob(newpathname, schema_entities + ["suggestion"], dironly)

    new_suggestions = set()
    suggestiontempl = op.basename(newpathname)
    filepaths = []
    tagdictlist = []
    _scan_requested_event = Event()

    def _is_candidate(filepath):
        if dironly is True:
            return op.isdir(filepath)
        else:
            return op.isfile(filepath)

    try:
        for filepath, tagdict in tag_glob_generator:
            if "suggestion" in tagdict and len(tagdict["suggestion"]) > 0:
                suggestionstr = suggestion_match.sub(tagdict["suggestion"], suggestiontempl)
                if op.isdir(filepath):
                    suggestionstr = op.join(suggestionstr, "")  # add trailing slash
                new_suggestions.add(suggestionstr)

            elif _is_candidate(filepath):
                filepaths.append(filepath)
                tagdictlist.append(tagdict)

            if _scan_requested_event.is_set():
                break

    except ValueError as e:
        print("Error scanning files: %s", e)

    tagsetdict = {}
    if len(tagdictlist) > 0:
        tagsetdict = {k: set(dic[k] for dic in tagdictlist) for k in tagdictlist[0] if k != "suggestion"}

    nfile = len(filepaths)

    p = inflect.engine()
    value = p.inflect(f"Found {nfile} plural('file', {nfile})")

    if len(tagsetdict) > 0:
        value += " "
        value += "for"
        value += " "
        tagmessages = [p.inflect(f"{len(v)} plural('{k}', {len(v)})") for k, v in tagsetdict.items()]
        value += p.join(tagmessages)

    return value, filepaths


class ColorButton(Button):
    """
    ColorButton

    A subclass of Button that includes a customizable color attribute.
    Sets current highlighting color by pressing the button.

    Attributes
    ----------
    color : str
        The color associated with the button, used for styling the background.

    Methods
    -------
    on_click(event)
        Handles the click event and sets the highlight color of a specific widget.
    """

    def __init__(self, color: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = color
        self.styles.background = color

    async def on_click(self, event: events.Click) -> None:
        path_widget = self.app.get_widget_by_id("input_prompt")
        path_widget.highlight_color = self.color


class PathPatternBuilder(DraggableModalScreen):
    """
    PathPatternBuilder class provides a modal screen to allow users to interactively specify path patterns.
    Consists of color button to switch between the highlight colors, the string itself, some edit buttons
    and Ok/Cancel buttons. The key component is the InputWithColoredSuggestions which allows the string highlighting
    and supports also pattern suggestions.

    Attributes
    ----------
    title_bar : TitleBar
        Component that displays the title of the modal screen.
    path : str
        The initial file path provided.
    highlight_colors : list of str
        List of colors available for highlighting.
    labels : list of str
        List of labels used for tagging and identifying segments of the path.
    pattern_match_results : dict
        Dictionary that stores the current pattern, feedback message, and matched files.
    original_value : str
        The original file path value before user modifications.
    mandatory_tag : str
        A mandatory tag that needs to be present in the path pattern.

    Methods
    -------
    __init__(path, highlight_colors=None, labels=None, title="X", *args, **kwargs)
        Initializes a new instance of the PathPatternBuilder class.
    on_mount()
        Called when the window is mounted and initializes UI components.
    deactivate_pressed_button()
        Deactivates the currently active button.
    activate_pressed_button(_id)
        Activates the button with the given ID.
    open_browse_window()
        Opens a file browser modal window.
    update_input(selected_path: str)
        Updates the input prompt with the selected path.
    reset_highlights()
        Resets all highlights in the input prompt.
    reset_all()
        Resets all data and highlights in the input prompt.
    submit_highlights()
        Submits the highlighted path for processing.
    _segment_highlighting_submitted(event)
        Updates pattern_match_results based on the output of various methods.
    activate_and_deactivate_press(event: Button.Pressed)
        Activates and deactivates buttons based on the pressed event.
    _ok(event: Button.Pressed)
        Confirms the selected pattern and dismisses the modal if valid.
    _close(event: Button.Pressed)
        Closes the modal without taking action.
    _remove_self()
        Displays a list of files matching the current pattern.
    on_key(event: events.Key)
        Handles keyboard input to navigate and toggle highlights.
    key_enter()
        Submits the current path pattern when Enter is pressed.
    key_escape()
        Dismisses the modal when Escape is pressed.
    """

    def __init__(
        self,
        path: str | Text,
        highlight_colors=None,
        labels=None,
        title="X",
        pattern_class=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.title_bar.title = title
        self.path = path.plain if isinstance(path, Text) else path
        self.highlight_colors = ["red", "green", "blue", "yellow", "magenta"] if highlight_colors is None else highlight_colors
        self.labels = ["subject", "Session", "Run", "Acquisition", "task"] if labels is None else labels
        self.pattern_match_results: dict = {"file_pattern": self.path, "message": "Found 0 files.", "files": []}
        self.original_value = path
        self.mandatory_tag = f"{{{self.labels[0]}}}"
        # TODO: since now we are always passing the particular pattern_class to the path_pattern_builder, we do not need
        # to pass colors and labels separately, thus this needs to be cleaned through the whole code
        self.pattern_class = pattern_class

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        colors_and_labels = dict(zip(self.highlight_colors, self.labels, strict=False))
        self.active_button_id = "button_" + self.labels[0]
        color_buttons = [
            ColorButton(label=item[1], color=item[0], id="button_" + item[1], classes="color_buttons")
            for item in colors_and_labels.items()
        ]
        color_buttons[0].add_class("activated")
        self.content.mount(
            Grid(
                *color_buttons,
                id="color_button_panel",
            ),
            HorizontalScroll(
                InputWithColoredSuggestions(
                    [(Text(self.path), self.path)],
                    prompt_default=self.path,
                    colors_and_labels=colors_and_labels,
                    top_parent=self,
                    id="path_widget",
                ),
                id="path_widget_container",
            ),
            Grid(
                Button("Browse", id="browse_button"),
                Button("Reset highlights", id="reset_button"),
                Button("Reset all", id="reset_all"),
                Button("Clear all", id="clear_all"),
                Button("Submit", id="submit_button"),
                id="button_panel",
            ),
            Container(
                Container(
                    Static("Found 0 files.", id="feedback"),
                    Button("👁", id="show_button", classes="icon_buttons"),
                    id="feedback_container",
                ),
                Container(Button("OK", id="ok_button"), Button("Cancel", id="cancel_button"), id="testtt"),
                id="feedback_and_confirm_panel",
            ),
        )
        self.get_widget_by_id("color_button_panel").styles.grid_size_columns = len(self.labels)

    def deactivate_pressed_button(self):
        """Fade the button when inactive."""
        if self.active_button_id is not None:
            self.get_widget_by_id(self.active_button_id).remove_class("activated")

    def activate_pressed_button(self, _id):
        """Light up the button when inactive."""
        clicked_color_button = self.get_widget_by_id(_id)
        clicked_color_button.add_class("activated")
        self.active_button_id = _id

    @on(Button.Pressed, "#browse_button")
    def open_browse_window(self):
        self.app.push_screen(FileBrowserModal(path_test_function=path_test_with_isfile_true), self.update_input)

    def update_input(self, selected_path: str) -> None:
        """Update the Prompt value."""
        if selected_path is not None:
            self.get_widget_by_id("input_prompt").value = str(selected_path)
            self.get_widget_by_id("input_prompt").original_value = str(selected_path)

    @on(Button.Pressed, "#reset_button")
    def reset_highlights(self):
        self.get_widget_by_id("input_prompt").reset_highlights()

    @on(Button.Pressed, "#reset_all")
    def reset_all(self):
        self.get_widget_by_id("input_prompt").reset_all()

    @on(Button.Pressed, "#clear_all")
    def clear_all(self):
        self.get_widget_by_id("input_prompt").value = ""

    @on(Button.Pressed, "#submit_button")
    def submit_highlights(self):
        self.get_widget_by_id("input_prompt").submit_path()

    @on(InputWithColoredSuggestions.Changed)
    @on(SegmentHighlighting.Submitted)
    @on(SegmentHighlighting.Changed)
    def _segment_highlighting_submitted(self, event):
        """Update the pattern_match_results dictionary based on the output of various methods."""
        if isinstance(event.value, Text):
            event_value = event.value.plain
            match_feedback_message, filepaths = evaluate_files(event_value)
            self.path = event_value
        else:
            match_feedback_message, filepaths = evaluate_files(event.value)
            self.path = event.value

        highlights = self.get_widget_by_id("input_prompt").current_highlights
        self.get_widget_by_id("feedback").update(match_feedback_message)
        self.get_widget_by_id("show_button").tooltip = match_feedback_message
        self.pattern_match_results = {
            "file_pattern": Text(self.path, spans=highlights),
            "message": match_feedback_message,
            "files": filepaths,
        }
        # Change outine from red to green if some files were found.
        if len(self.pattern_match_results["files"]) > 0:
            self.query_one(SelectCurrentWithInputAndSegmentHighlighting).styles.outline = ("solid", "green")
        else:
            self.query_one(SelectCurrentWithInputAndSegmentHighlighting).styles.outline = ("solid", "red")

    @on(Button.Pressed, ".color_buttons")
    def activate_and_deactivate_press(self, event: Button.Pressed):
        self.deactivate_pressed_button()
        self.activate_pressed_button(event.button.id)

    @on(Button.Pressed, "#ok_button")
    def _ok(self, event: Button.Pressed):
        # Here wer try to catch the Marshmallow schema error, if the extension is wrong
        try:
            path = (
                self.pattern_match_results["file_pattern"].plain
                if isinstance(self.pattern_match_results["file_pattern"], Text)
                else self.pattern_match_results["file_pattern"]
            )
            self.pattern_class.check_extension(path)
            self._ok_part_two()
        except Exception as e:
            self.app.push_screen(
                Confirm(
                    convert_validation_error_to_string(e),
                    left_button_text=False,
                    right_button_text="OK",
                    right_button_variant="default",
                    title="File pattern error",
                    classes="confirm_error",
                )
            )

    def _ok_part_two(self):
        # if all is good from '_ok', continue here
        if self.mandatory_tag not in self.pattern_match_results["file_pattern"]:
            self.app.push_screen(
                Confirm(
                    f"Mandatory tag missing!\n Set {self.mandatory_tag}!",
                    left_button_text=False,
                    right_button_text="OK",
                    right_button_variant="default",
                    title="Missing name",
                    classes="confirm_error",
                )
            )
        else:
            self.dismiss(self.pattern_match_results)

    @on(Button.Pressed, "#cancel_button")
    def _close(self, event: Button.Pressed):
        self.dismiss(False)

    @on(Button.Pressed, "#show_button")
    def _remove_self(self):
        self.app.push_screen(ListOfFiles(self.pattern_match_results))

    async def on_key(self, event: events.Key):
        """Handles keyboard events to move the cursor and toggle highlighting mode."""
        path_widget = self.get_widget_by_id("input_prompt")
        if event.key in ["1", "2", "3", "4", "5"]:
            # Set highlight color based on key pressed.
            index = int(event.key) - 1
            path_widget.highlight_color = self.highlight_colors[index]
            self.deactivate_pressed_button()
            self.activate_pressed_button("button_" + self.labels[index])

    def key_enter(self):
        self.get_widget_by_id("input_prompt").submit_path()

    def key_escape(self):
        self.dismiss(False)
