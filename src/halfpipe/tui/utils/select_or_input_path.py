# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from typing import Iterable, TypeVar, Union

from rich.console import RenderableType
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal

# from textual.keys import _get_key_display
from textual.message import Message
from textual.reactive import var
from textual.widgets import Input, OptionList, Select, Static
from textual.widgets._select import EmptySelectError, NoSelection
from textual.widgets.option_list import Option
from typing_extensions import TypeAlias

SelectType = TypeVar("SelectType")
"""The type used for data in the Select."""
SelectOption: TypeAlias = "tuple[str, SelectType]"
"""The type used for options in the Select."""


def find_common_start(strings):
    """
    Parameters
    ----------
    strings : list of str
        A list of strings to find the common starting substring among them.

    Returns
    -------
    str
        The longest common starting substring found in all the input strings.
        If no common start exists, returns an empty string.
    """
    if not strings:
        return ""

    common_start = strings[0]
    for s in strings[1:]:
        # Reduce the common_start while it's not a prefix of s
        while not s.startswith(common_start):
            common_start = common_start[:-1]
            if not common_start:
                return ""
    return common_start


def create_path_option_list(base="/home/tomas/github/", include_base=False):
    """
    Parameters
    ----------
    base : str, optional
        The base directory path, default is "/home/tomas/github/".
    include_base : bool, optional
        Determines whether to include the base directory in the returned list, default is False.
    """
    filepaths = [base] if include_base else []
    if os.access(base, os.W_OK):
        for f in os.scandir(base):
            filepath = f.path
            if f.is_dir():
                filepath += "/"
            filepaths.append(filepath)
        filepaths.sort()
    return filepaths


class SelectOverlay(OptionList):
    """
    class SelectOverlay(OptionList):
        A class representing an overlay for selecting options, extending OptionList.

    Attributes
    ----------
    BINDINGS : list
        Key bindings specific for the overlay, such as the escape key to dismiss.

    Methods
    -------
    select(index: int | None)
        Move selection.

    action_dismiss()
        Dismiss the overlay.

    _on_blur(self, _event: events.Blur)
        Dismiss the overlay when it loses focus.

    on_option_list_option_selected(self, event: OptionList.OptionSelected)
        Inform parent when an option is selected.

    async on_key(self, event: events.Key)
        Handle key events within the overlay.
    """

    BINDINGS = [("escape", "dismiss")]

    @dataclass
    class Dismiss(Message):
        """Inform ancestor the overlay should be dismissed."""

        lost_focus: bool = False
        """True if the overlay lost focus."""

    @dataclass
    class UpdateSelection(Message):
        """Inform ancestor the selection was changed."""

        option_index: int
        """The index of the new selection."""

    @dataclass
    class Typing(Message):
        """Inform ancestor the overlay should be dismissed."""

        value: str
        """True if the overlay lost focus."""

    def select(self, index: int | None) -> None:
        """Move selection.

        Args:
            index: Index of new selection.
        """
        self.highlighted = index
        self.scroll_to_highlight(top=True)

    def action_dismiss(self) -> None:
        """Dismiss the overlay."""
        self.post_message(self.Dismiss())

    def _on_blur(self, _event: events.Blur) -> None:
        """On blur we want to dismiss the overlay."""
        self.post_message(self.Dismiss(lost_focus=True))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Inform parent when an option is selected."""
        event.stop()
        self.post_message(self.UpdateSelection(event.option_index))

    async def on_key(self, event: events.Key) -> None:
        """This allows to typing in the prompt when the focus is on the overlay."""
        if any(mod in event.key for mod in ["ctrl", "alt", "shift"]):
            return

        # List of specific disallowed keys
        disallowed_keys = [
            "up",
            "down",
            "left",
            "right",
            "home",
            "end",
            "pageup",
            "pagedown",
            "tab",
            "delete",
            "insert",
            "enter",
            "return",
            "space",
            "capslock",
            "numlock",
            "scrolllock",
        ] + [f"F{i}" for i in range(1, 13)]  # Function keys

        if event.key in disallowed_keys:
            # Ignore disallowed keys
            pass
        else:
            # Process allowed keys here
            if event.key == "escape":
                event.stop()
            self.post_message(self.Typing(event.key))


class MyInput(Input):
    """
    MyInput(shrink=True, id=None, classes=None)

    A custom input class that allows additional functionality such as shrink.

    Parameters
    ----------
    shrink : bool, optional
        If True, enables the shrink property for the input, by default True.
    id : str or None, optional
        An optional identifier for the input instance, by default None.
    classes : str or None, optional
        Additional CSS classes to apply to the input instance, by default None.
    """

    def __init__(self, shrink: bool = True, id: str | None = None, classes: str | None = None, **kwargs) -> None:
        super().__init__(id=id, classes=classes, **kwargs)
        self.shrink = shrink

    class Toggle(Message):
        """Request toggle overlay."""

    async def _on_click(self, event: events.Click) -> None:
        """Inform ancestor we want to toggle."""
        self.post_message(self.Toggle())


class MyStatic(Static):
    """
    class Toggle(Message):
    """

    class Toggle(Message):
        """Request toggle overlay."""

    async def _on_click(self, event: events.Click) -> None:
        """Inform ancestor we want to toggle."""
        self.post_message(self.Toggle())


class SelectCurrentWithInput(Horizontal):
    """
    A custom widget that combines a selectable input field with additional
    UI elements, such as toggling arrows, and handles various user interactions.

    Attributes
    ----------
    DEFAULT_CSS : str
        Default CSS styling for the widget.
    has_value : var[bool]
        A flag indicating whether the input field
    """

    DEFAULT_CSS = """
    SelectCurrentWithInput {
        height: 3;
        width: 100%;
        margin: 0 0 0 0;
        padding: 0 0 0 2;
        border: none;
        outline: tall $accent;
        content-align: center bottom;
                background: transparent;
    }
    SelectCurrentWithInput MyInput#label {
        width: 1fr;
        height: 3;
        color: $text-disabled;
        background: transparent;
        outline-top: $accent tall;
        outline-bottom: $accent tall;
        padding: 1;
        border: none;

    }
    SelectCurrentWithInput.-has-value MyInput#label {
        color: $text;
    }
    SelectCurrentWithInput .arrow {
        box-sizing: content-box;
        width: 1;
        height: 2;
        padding: -1 1 0 0;
        margin: 1 1 1 -1;
        color: red;
        background: transparent;
        content-align: center bottom;

    }
    """

    @dataclass
    class PromptChanged(Message):
        """Inform ancestor the selection was changed."""

        value: str

    @dataclass
    class PromptCloseOverlay(Message):
        """Inform ancestor the selection was changed."""

    has_value: var[bool] = var(False)

    class Toggle(Message):
        """Request toggle overlay."""

    def __init__(self, placeholder: str, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield MyInput(name="select_input", placeholder=self.placeholder, id="input_prompt")
        yield MyStatic("▼", classes="arrow down-arrow")
        yield MyStatic("▲", classes="arrow up-arrow")

    def update(self, new_placeholder: RenderableType | NoSelection) -> None:
        """Update the content in the widget.

        Args:
            label: A renderable to display, or `None` for the placeholder.
        """
        self.new_placeholder = new_placeholder
        # This will change the MyInput widget value also and triggers "on_input_changed"
        self.get_widget_by_id("input_prompt").value = (
            self.placeholder if isinstance(new_placeholder, NoSelection) else new_placeholder
        )

    def on_input_changed(self, message):
        """When user types to prompt this method is triggered.
        when user selects option this method is triggered.
        """
        path = self.get_widget_by_id("input_prompt").value
        self.post_message(self.PromptChanged(path))

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.post_message(self.PromptCloseOverlay())
            event.stop()

    def _watch_has_value(self, has_value: bool) -> None:
        """Toggle the class."""
        self.set_class(has_value, "-has-value")


class SelectOrInputPath(Select):
    """
    SelectOrInputPath: A customizable selection widget that allows users to either select from a list or input a path.

    Attributes
    ----------
    DEFAULT_CSS : str
        The default CSS styling for the widget.
    expanded : var[bool]
    """

    DEFAULT_CSS = """
    SelectOrInputPath:focus > SelectCurrent {
        border: tall $accent;
    }

    SelectOrInputPath > SelectOverlay {
        width: 100%;
        display: none;
        height: auto;
        max-height: 12;
        overlay: screen;
        constrain: none inside;
    }

    SelectOrInputPath .up-arrow {
        display:none;
    }

    Select.-expanded .down-arrow {
        display:none;
    }

    SelectOrInputPath.-expanded .up-arrow {
        display: block;
    }

    SelectOrInputPath.-expanded > SelectOverlay {
        display: block;
    }

    SelectOrInputPath.-expanded > SelectCurrent {
        border: tall $accent;
    }
    """

    expanded: var[bool] = var(False, init=False)
    """True to show the overlay, otherwise False."""
    prompt: var[str] = var[str]("Select")
    """The prompt to show when no value is selected."""
    value: var[SelectType | NoSelection] = var[Union[SelectType, NoSelection]]("")
    """The value of the selection."""

    input_class = SelectCurrentWithInput

    @dataclass
    class PromptChanged(Message):
        """Inform ancestor the selection was changed."""

        value: str

    def __init__(self, options, *, prompt_default: str = "", top_parent=None, id=None, classes=None):
        # pass default as prompt to super since this will be used as an fixed option in the optionlist
        super().__init__(options, prompt=prompt_default, id=id, classes=classes)
        self.top_parent = top_parent
        self._value: str = prompt_default
        self.prompt_default = prompt_default
        self._setup_variables_for_options(options)

    def prepare_compose(self):
        yield self.input_class(self._value)
        yield SelectOverlay()

    def compose(self) -> ComposeResult:
        # Collect results from prepare_compose
        for widget in self.prepare_compose():
            yield widget

    def _setup_variables_for_options(
        self,
        options: Iterable[tuple[RenderableType, SelectType]],
    ) -> None:
        """Setup function for the auxiliary variables related to options.

        This method sets up `self._options` and `self._legal_values`.
        """
        self._options: list[tuple[RenderableType, SelectType | NoSelection]] = []
        self._options.extend(options)

        if not self._options:
            raise EmptySelectError("Select options cannot be empty if selection can't be blank.")

        self._legal_values: set[SelectType | NoSelection] = {value for _, value in self._options}

    def _setup_options_renderables(self) -> None:
        """Sets up the `Option` renderables associated with the `Select` options."""
        # if _allow_blank is true, then the self.BLANK is appended and here we use it to put the default into the options
        self._select_options: list[Option] = [
            (Option(Text(self.prompt_default, style="dim")) if value == self.prompt_default else Option(prompt))
            for prompt, value in self._options
        ]

        option_list = self.query_one(SelectOverlay)
        option_list.clear_options()
        for option in self._select_options:
            option_list.add_option(option)

    def _init_selected_option(self, hint) -> None:
        """Initialises the selected option for the `Select`."""
        # If allow_blank then no default is available and use first option in the list
        if hint == "" and self._allow_blank:
            hint = self._options[0][1]
        self.value = hint

    async def on_key(self, event: events.Key) -> None:
        """Called when the user presses a key."""
        # Path suggestions
        if event.key == "shift+right":
            select_current = self.query_one(self.input_class)
            myinput = select_current.get_widget_by_id("label")
            current_path = myinput.value
            strings = (
                create_path_option_list(current_path.rsplit("/", 1)[0])
                if current_path.count("/") > 1
                else create_path_option_list("/")
            )
            strings = [f for f in strings if current_path in f]
            myinput.value = find_common_start(strings)
            myinput.cursor_position = len(myinput.value)
        # Close the overlay.
        select_overlay = self.query_one(SelectOverlay)
        if event.key == "esc":
            self.expanded = False
        # Opens the overlay.
        if event.key == "down":
            self.expanded = True
            select_overlay.focus()

    @on(input_class.PromptCloseOverlay)
    def _select_current_with_input_prompt_close_overlay(self, event: SelectCurrentWithInput.PromptCloseOverlay):
        """When the Overlay is closed while the focus is on the input widget, keep the overlay closed."""
        if self.input_class == SelectCurrentWithInput:
            self.expanded = False

    @on(input_class.PromptChanged)
    def _select_current_with_input_prompt_changed(self, event: SelectCurrentWithInput.PromptChanged):
        """Runs when input prompt is changed."""

        if self.input_class == SelectCurrentWithInput:
            path = event.value
            self.value = path
            self.post_message(self.PromptChanged(path))
            if os.path.exists(path):
                if path.endswith("/") and os.path.isdir(path):
                    # When user selects option this is triggered
                    path_suggestions = create_path_option_list(base=path)
                    if path_suggestions != []:
                        self._setup_variables_for_options([(f, f) for f in path_suggestions])
                        self._setup_options_renderables()
            else:
                # When user types to prompt this is triggered
                filepaths = []
                path_uncomplete = path
                path = path.rsplit("/", 1)[0] if path.count("/") > 1 else "/"
                if os.path.exists(path) and os.path.isdir(path):
                    for f in os.scandir(path):
                        filepath = f.path
                        if f.is_dir():
                            filepath += "/"
                        if filepath.startswith(path_uncomplete):
                            filepaths.append(filepath)
                        filepaths.sort()
                    self.expanded = True
                    if filepaths != []:
                        self._setup_variables_for_options([(f, f) for f in filepaths])
                        self._setup_options_renderables()
            if os.path.isfile(path):
                self.expanded = False

    @on(SelectOverlay.UpdateSelection)
    def _update_selection(self, event: SelectOverlay.UpdateSelection) -> None:
        """Update the current selection."""
        event.stop()
        value = self._options[event.option_index][1]
        if value != self.value:
            self.value = value
            self.post_message(self.Changed(self, value))

    @on(SelectOverlay.Typing)
    async def _select_overlay_typing(self, event: SelectOverlay.Typing):
        """Passes the typing activity on overlay to the main widget and update the path."""
        select_current = self.query_one(self.input_class)
        #  myinput = select_current.query_one(MyInput)
        myinput = select_current.get_widget_by_id("input_prompt")
        #
        myinput_current_value = myinput.value
        if event.value == "backspace":
            myinput.value = myinput_current_value[:-1]
        elif event.value == "escape":
            self.expanded = False
        else:
            if event.value.islower() and len(event.value) == 1:
                myinput.value = myinput_current_value + event.value
            else:
                myinput.value = myinput_current_value + self.app.get_key_display(event.value)

    @on(MyInput.Toggle)
    def _my_input_toggle(self, event: MyInput.Toggle):
        event.stop()
        self.expanded = not self.expanded

    @on(MyStatic.Toggle)
    def _my_static_toggle(self, event: MyStatic.Toggle):
        event.stop()
        self.expanded = not self.expanded

    # this is when a selection is made to update the input (prompt)
    def _watch_value(self, value: SelectType | NoSelection) -> None:
        """Update the current value when it changes."""
        # When user selects option this is triggered
        self._value = str(value)
        select_current = self.query_one(self.input_class)
        for index, (_, _value) in enumerate(self._options):
            if _value == value:
                select_overlay = self.query_one(SelectOverlay)
                select_overlay.highlighted = index
                select_current.update(value)
                break
        self.post_message(self.PromptChanged(self.value))

    def _watch_expanded(self, expanded: bool) -> None:
        """Display or hide overlay."""
        # unchanged from the super, except SelectCurrent > self.input_class and no BLANK
        overlay = self.query_one(SelectOverlay)
        self.set_class(expanded, "-expanded")
        select_current = self.query_one(self.input_class)
        if expanded:
            value = self.value
            select_current.has_value = False
            for index, (_prompt, prompt_value) in enumerate(self._options):
                if value == prompt_value:
                    overlay.select(index)
                    break
        else:
            select_current.has_value = True

    def _watch_prompt(self, prompt: str) -> None:
        """Prompt variable is not used in this subclass"""

    def action_show_overlay(self) -> None:
        """Show the overlay."""
        # Unchanged from the super, except SelectCurrent > self.input_class and has value is not used here
        self.expanded = True

    def _validate_value(self, value: SelectType | NoSelection) -> SelectType | NoSelection:
        return value

    def change_prompt_from_parrent(self, new_value):
        if new_value != "/":
            if os.path.isdir(new_value):
                new_value += "/"

        select_current = self.query_one(self.input_class)
        select_current.update(new_value)
