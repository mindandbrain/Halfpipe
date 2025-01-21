# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Select, Static, Switch

from .confirm_screen import Confirm
from .custom_switch import TextSwitch


class SwitchWithInputBox(Widget):
    """
    class SwitchWithInputBox(Widget):
        A widget that combines a text input box with a toggle switch, allowing
        for reactive UI changes based on the state of the switch and the input
        value.

    Attributes
    ----------
    value : reactive[bool]
        The reactive value associated with the input box.
    switch_value : reactive[bool]
        The reactive value associated with the switch.

    Events
    ------
    Changed
        Event fired when the input box value changes.
    SwitchChanged
        Event fired when the switch value changes.

    Methods
    -------
    __init__(label="", value: str | None = None, switch_value: bool = False, **kwargs)
        Initializes the widget with an optional label, input value, and switch state.
    watch_value()
        Posts a Changed message when the input value changes.
    watch_switch_value()
        Posts a SwitchChanged message when the switch value changes.
    compose() -> ComposeResult
        Composes and yields the widget components (label, switch, input box).
    update_label(label)
        Updates the label component of the widget.
    on_mount()
        Configures the visibility of the input box based on the initial switch value.
    on_switch_changed(message)
        Handles the Switch.Changed event to update the switch value and input box visibility.
    update_from_input()
        Updates the widget's input value based on changes in the input box.

    dataclass Changed(Message):
        Message indicating that the input value has changed.

        Attributes
        ----------
        switch_with_input_box : SwitchWithInputBox
            Reference to the SwitchWithInputBox instance.
        value : str
            The new value of the input box.

        Properties
        ----------
        control
            Alias for `switch_with_input_box`.

    dataclass SwitchChanged(Message):
        Message indicating that the switch value has changed.

        Attributes
        ----------
        switch_with_select : SwitchWithInputBox
            Reference to the SwitchWithInputBox instance.
        switch_value : bool
            The new value of the switch.

        Properties
        ----------
        control
            Alias for `switch_with_input_box`.
    """

    value: reactive[str] = reactive(None, init=False)
    switch_value: reactive[bool] = reactive(None, init=False)

    @dataclass
    class Changed(Message):
        switch_with_input_box: "SwitchWithInputBox"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.switch_with_input_box

    @dataclass
    class SwitchChanged(Message):
        switch_with_input_box: "SwitchWithInputBox"
        switch_value: bool

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.switch_with_input_box

    def __init__(
        self, label="", value: str | None = None, switch_value: bool = True, id: str | None = None, classes: str | None = None
    ) -> None:
        self.label = label
        self._reactive_switch_value = switch_value
        self._reactive_value = str(value) if value is not None else None

        super().__init__(id=id, classes=classes)

    def watch_value(self) -> None:
        self.post_message(self.Changed(self, self.value))

    def watch_switch_value(self) -> None:
        self.post_message(self.SwitchChanged(self, self.switch_value))

    def compose(self) -> ComposeResult:
        yield Grid(
            Static(self.label),
            TextSwitch(value=self.switch_value, id="the_switch"),
            Input(value=self.value, placeholder="Value", id="input_switch_input_box"),
        )

    def update_label(self, label):
        self.query_one(Static).update(label)

    def update_value(self, value):
        self.get_widget_by_id("input_switch_input_box").value = value

    def update_switch_value(self, value):
        self.get_widget_by_id("the_switch").value = value

    def on_mount(self):
        if self.switch_value is True:  # or self.value is not None:
            self.get_widget_by_id("input_switch_input_box").styles.visibility = "visible"
        else:
            self.get_widget_by_id("input_switch_input_box").styles.visibility = "hidden"

    # def on_switch_changed(self):
    # last_switch = self.query("Switch").last()
    # if last_switch.value:
    # self.get_widget_by_id("input_switch_input_box").styles.visibility = "visible"
    # else:
    # self.get_widget_by_id("input_switch_input_box").styles.visibility = "hidden"
    # self.value = 0

    @on(Switch.Changed)
    def on_switch_changed(self, message):
        self.switch_value = message.value
        if self.switch_value is True:
            self.get_widget_by_id("input_switch_input_box").styles.visibility = "visible"
        else:
            self.get_widget_by_id("input_switch_input_box").styles.visibility = "hidden"

    @on(Input.Changed, "#input_switch_input_box")
    def update_from_input(self):
        self.value = self.get_widget_by_id("input_switch_input_box").value


class SwitchWithSelect(SwitchWithInputBox):
    """
    SwitchWithSelect Class
    Inherits from SwitchWithInputBox to add a selection component along with a switch.

    Attributes
    ----------
    label : str
        The label to display alongside the switch and select components.
    options : list
        The options to display in the select component. Defaults to an empty list if not provided.

    Methods
    -------
    compose()
        Generates the components (Grid, Static, TextSwitch, and Select) to be displayed.
    update_from_input()
        Updates the value based on the selected item from the select component.

    Changed(Message)
        A message class used to notify when the switch_with_select component's value has changed.

    SwitchChanged(Message)
        A message class used to notify when the switch_with_select component's switch value has changed.
    """

    @dataclass
    class Changed(Message):
        switch_with_select: "SwitchWithSelect"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.switch_with_select

    @dataclass
    class SwitchChanged(Message):
        switch_with_select: "SwitchWithSelect"
        switch_value: bool

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.switch_with_select

    def __init__(
        self,
        label="",
        switch_value: bool = True,
        options: list | None = None,
        default_option=None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.label = label
        super().__init__(label=label, id=id, classes=classes)
        self.options = [] if options is None else options
        self.default_option = self.options[0][1] if default_option is None else default_option
        self.switch_value = switch_value
        self.value = self.default_option

    def compose(self) -> ComposeResult:
        yield Grid(
            Static(self.label),
            TextSwitch(value=self.switch_value),
            Select(
                [(str(value[0]), value[1]) for value in self.options],
                value=self.default_option,
                allow_blank=False,
                id="input_switch_input_box",
            ),
        )

    @on(Select.Changed, "#input_switch_input_box")
    def update_from_input(self):
        self.value = str(self.get_widget_by_id("input_switch_input_box").value)


class LabelWithInputBox(Widget):
    """
    A widget class that combines a label with an input box that reacts to changes.

    value : reactive[bool]
        A reactive property to hold the value of the input box, initially set to None.

    Attributes
    ----------
    label_with_input_box : LabelWithInputBox
        The LabelWithInputBox instance that triggered the change message.
    value : str
        The new value of the input box.
    control : LabelWithInputBox
        Property that provides an alias for accessing the associated LabelWithInputBox instance.
    """

    value: reactive[bool] = reactive(None, init=False)

    @dataclass
    class Changed(Message):
        label_with_input_box: "LabelWithInputBox"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.label_with_input_box

    def __init__(self, label="", value: str | None = None, **kwargs) -> None:
        self.label = label
        self._reactive_value = str(value) if value is not None else None
        super().__init__(**kwargs)

    def watch_value(self) -> None:
        self.post_message(self.Changed(self, self.value))

    def compose(self) -> ComposeResult:
        yield Grid(
            Static(self.label),
            Input(value=self.value, placeholder="Value", id="input_label_input_box"),
        )

    def update_label(self, label):
        self.query_one(Static).update(label)

    @on(Input.Changed, "#input_label_input_box")
    def update_from_input(self):
        self.value = str(self.get_widget_by_id("input_label_input_box").value)


class LabelledSwitch(Widget):
    """
    LabelledSwitch Class

    A widget that consists of a label and a text switch, with additional functionality to display a help message.

    Methods
    -------
    __init__(label, value, help_message="Explain the functionality", id=None)
        Initializes the LabelledSwitch object with a label, value, help message, and an optional id.

    compose()
        Creates and returns the layout of the widget, including the static label and text switch.

    update_value(value)
        Updates the value of the switch.

    _on_help_button_pressed()
        Event handler that triggers when the help button is pressed, displaying a help modal.

    _on_select(event)
        Event handler that triggers when the switch value changes, posting a Changed message.
    """

    def __init__(self, label, value, help_message="Explain the functionality", id=None):
        super().__init__(id=id)
        self.label = label
        self.value = value
        self.help_message = help_message

    def compose(self) -> ComposeResult:
        yield Grid(
            #   Button("❓", id="help_button", classes="icon_buttons"),
            Static(self.label),
            TextSwitch(self.value),
        )

    def update_value(self, value):
        self.query_one(Switch).value = value

    @on(Button.Pressed, "#help_button")
    def _on_help_button_pressed(self):
        self.app.push_screen(
            Confirm(
                self.help_message,
                left_button_text=False,
                right_button_text="OK",
                right_button_variant="default",
                title="Help",
                id="help_modal",
                # classes="confirm_warning",
            )
        )

    @on(Switch.Changed)
    def _on_select(self, event):
        self.post_message(self.Changed(event.value, self))

    @dataclass
    class Changed(Message):
        """Inform ancestor the selection was changed."""

        value: str
        labelled_switch: LabelledSwitch

        @property
        def control(self) -> LabelledSwitch:
            """The Select that sent the message."""
            return self.labelled_switch
