# -*- coding: utf-8 -*-
from dataclasses import dataclass

import numpy as np
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, RadioButton

from ._radio_set2 import RadioSet
from .confirm_screen import Confirm
from .draggable_modal_screen import DraggableModalScreen


class MultipleRadioSet(Widget):
    """
    class MultipleRadioSet(Widget):
        A widget that creates a set of radio buttons arranged in a table format,
        with options specified by horizontal and vertical label sets.

    Attributes
    ----------
    horizontal_label_set : list
        The list of labels for horizontal radio button groups.
    vertical_label_set : list
        The list of labels for vertical radio button groups.

    Methods
    -------
    compose()
        Composes the widget by generating a table of radio buttons labeled by
        the horizontal and vertical labels provided.
    on_mount()
        Called when the widget is initialized to set the widths and alignment
        of radio buttons.
    get_selections()
        Retrieves the currently selected radio buttons for each row.

    __init__(id=None, classes=None, horizontal_label_set=None, vertical_label_set=None)
        Initializes the widget with optional ID, classes, horizontal and vertical label sets.

    Parameters
    ----------
    id : str, optional
        An identifier for the widget instance (default is None).
    classes : str, optional
        Space-separated list of style class names (default is None).
    horizontal_label_set : list, optional
        List of labels for the horizontal radio buttons (default is pre-defined labels).
    vertical_label_set : list, optional
        List of labels for the vertical radio buttons (default is pre-defined labels).

    compose()
        Constructs the layout of the widget with horizontal and vertical labels.

    on_mount()
        Configures the width and content alignment of each radio button
        after the widget is mounted.

    get_selections()
        Returns the selected radio buttons for each row in a dictionary.

    Returns
    -------
    dict
        A dictionary mapping each vertical label to its selected radio button.
    """

    @dataclass
    class Changed(Message):
        multiple_radio_set: "MultipleRadioSet"
        row: int
        column: int

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.multiple_radio_set

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
        horizontal_label_set: None | list = None,
        vertical_label_set: None | list = None,
        default_value_column: int = 0,
        unique_first_column=False,
    ):
        super().__init__(id=id, classes=classes)
        self.horizontal_label_set = (
            horizontal_label_set
            if horizontal_label_set is not None
            else ["h_label1", "h_lab2", "h_long_label3", "4", "h_label5"]
        )
        self.horizontal_label_set[-1] = self.horizontal_label_set[-1] + "  "
        self.vertical_label_set = (
            vertical_label_set if vertical_label_set is not None else ["v_label1", "v_long_label2", "v_label3", "v_label4"]
        )
        self.default_value_column = default_value_column
        self.unique_first_column = unique_first_column
        self.last_unique_selection = "row_radio_sets_0"

    def compose(self) -> ComposeResult:
        vmax_length = max([len(i) for i in self.vertical_label_set])
        hmax_vertical_length = 1

        # modify the h labels so that if there is a label on multiple lines, the longest line becomes wrapped with spaces
        for i, h_val in enumerate(self.horizontal_label_set):
            split_label = [h for h in h_val.split("\n")]
            hmax_vertical_length = max([hmax_vertical_length, len(split_label)])
            index_longest_line = np.argmax([len(h) for h in split_label])
            split_label[index_longest_line] = "  " + split_label[index_longest_line] + "  "
            self.horizontal_label_set[i] = "\n".join(split_label)

        # with  ScrollableContainer(id='top_container'):
        with Horizontal(id="h_label_container"):
            for h_label in [" " + " " * (vmax_length + 2)] + self.horizontal_label_set:
                this_label = Label(h_label, classes="h_labels")
                # set height of the hlabels to the one with the most lines
                this_label.styles.height = hmax_vertical_length
                yield this_label
        for i, v_label in enumerate(self.vertical_label_set):
            with Horizontal(classes="radio_table_rows"):
                yield Label(v_label + " " * (vmax_length - len(v_label)) + "  ", classes="v_labels")
                with RadioSet(id="row_radio_sets_" + str(i)):
                    for j, _ in enumerate(self.horizontal_label_set):
                        # if self.unique_first_column is True and j == 0:
                        #     yield RadioButton(id="radio_column_" + str(j), value=True)
                        # else:
                        #     yield RadioButton(id="radio_column_" + str(j), value=(j + 1 - self.default_value_column))
                        # yield RadioButton(id="radio_column_" + str(j), classes="radio_column_" + str(j), value=(j + 1 -
                        # self.default_value_column))
                        is_first_column = True if (self.unique_first_column and i == 0 and j == 0) else False
                        value = 1 if is_first_column else (j + 1 - self.default_value_column)
                        print("v_labelv_labelv_label", v_label)
                        print("vvvvvvvvvvvvvvvvvv value", value)
                        print("jjjjjjjjjjjjjjjjj", j)
                        print("ooooooooooooooooooo", is_first_column)
                        print("--------------------------------------")
                        yield RadioButton(id=f"radio_column_{j}", value=value)

    def on_mount(self):
        for i, h_val in enumerate(self.horizontal_label_set):
            for this_radio_button in self.query("#radio_column_" + str(i)):
                # if there is a line break in the label, we count the length of the longest line
                h_val_length = max([len(h) for h in h_val.split("\n")])
                this_radio_button.styles.width = h_val_length + 1
                this_radio_button.styles.content_align = ("center", "middle")

    def get_selections(self):
        selections = {}
        for i, v_val in enumerate(self.vertical_label_set):
            # for this_radio_set in self.query("#row_radio_sets_" + str(i)):
            # selections[v_val] = this_radio_set._selected
            selections[v_val] = [v.value for v in self.get_widget_by_id("row_radio_sets_" + str(i)).query(RadioButton)]
        return selections

    @on(RadioSet.Changed)
    def on_radio_set_changed(self, message):
        # Simplify repeated access to widget properties
        def update_pressed_button(widget_id, column_id):
            widget = self.get_widget_by_id(widget_id)
            widget._pressed_button.value = False
            widget._pressed_button = widget.get_widget_by_id(column_id)

        def update_radio_columns(widget_id, active_column):
            widget = self.get_widget_by_id(widget_id)
            for i, _ in enumerate(self.horizontal_label_set):
                column_id = f"radio_column_{i}"
                widget.get_widget_by_id(column_id).value = i == active_column

        print("mnmmmmmmmmmmmmmmmmmmm", message.control.id)
        print("vvvvvvvvvvvvvvvvvvvvvvvv", message.index)
        print("seeeee", self.get_selections())
        should_post_message = True  # Flag to control whether the message should be posted

        if message.index == 0 and message.control.id != self.last_unique_selection and self.unique_first_column is True:
            if self.last_unique_selection is not None:
                # Update the pressed button for the message control and last unique selection
                update_pressed_button(message.control.id, "radio_column_0")
                update_pressed_button(self.last_unique_selection, "radio_column_1")

                # Update the radio columns for the message control and last unique selection
                update_radio_columns(message.control.id, active_column=0)
                update_radio_columns(self.last_unique_selection, active_column=1)

            self.last_unique_selection = message.control.id
            self.post_message(self.Changed(self, message.control.id, message.index))

        elif message.control.id == self.last_unique_selection and self.unique_first_column is True:
            self.app.push_screen(
                Confirm(
                    "Specify exactly one variables for the first column",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Missing images",
                    id="missing_images_modal",
                    classes="confirm_warning",
                )
            )
            update_pressed_button(message.control.id, "radio_column_0")
            update_radio_columns(message.control.id, active_column=0)
            should_post_message = False  # Prevent posting the message in this case

        if should_post_message:
            self.post_message(self.Changed(self, message.control.id, message.index))

    # def impose_column_uniqueness(self):


class MultipleRadioSetModal(DraggableModalScreen):
    """
    MultipleRadioSetModal
    ---------------------

    A modal dialog that allows the user to assign field maps to functional images
    using a set of horizontally and vertically labeled radio buttons. This modal
    is draggable and contains an 'OK' button to submit the selections.

    Parameters
    ----------
    title : str, default "Field maps to functional images"
        The title of the modal dialog.
    id : str or None, default None
        The unique identifier for this modal instance.
    classes : str or None, default None
        Additional CSS classes to style this modal.
    width : optional
        The width of the modal.
    horizontal_label_set : list or None, default None
        The labels to be used for the horizontal radio button set.
    vertical_label_set : list or None, default None
        The labels to be used for the vertical radio button set.

    Methods
    -------
    on_mount() :
        Asynchronously mounts the main content and UI elements in the modal.

    ok() :
        Event handler for the 'OK' button which captures the
        selections made by the user and then dismisses the modal.
    """

    CSS_PATH = ["tcss/confirm.tcss"]

    def __init__(
        self,
        title="Field maps to functional images",
        id: str | None = None,
        classes: str | None = None,
        width=None,
        horizontal_label_set: None | list = None,
        vertical_label_set: None | list = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.title_bar.title = title
        self.horizontal_label_set = (
            horizontal_label_set
            if horizontal_label_set is not None
            else ["h_label1", "h_lab2", "h_long_label3", "4", "h_label5"]
        )
        self.vertical_label_set = (
            vertical_label_set if vertical_label_set is not None else ["v_label1", "v_long_label2", "v_label3", "v_label4"]
        )

    async def on_mount(self) -> None:
        await self.content.mount(
            Label("Assign field maps to functional images:", id="instructions"),
            ScrollableContainer(
                MultipleRadioSet(horizontal_label_set=self.horizontal_label_set, vertical_label_set=self.vertical_label_set),
                id="outer_table_container",
            ),
            Horizontal(Button("OK", id="ok"), classes="button_grid"),
        )

    @on(Button.Pressed, "#ok")
    def ok(self):
        selections = self.query_one(MultipleRadioSet).get_selections()
        self.dismiss(selections)


class Main(App):
    """
    Class for testing.

    Attributes
    ----------
    CSS_PATH : str
        Path to the CSS file to be used for styling.

    Methods
    -------
    compose():
        Defines the components to be rendered by the application.

    on_button_show_modal_pressed(self):
        Event handler for the button with id 'show_modal' to display a modal with multiple radio sets.

    on_button_pressed(self):
        Event handler for the button with id 'ok' to query and process the current radio set selections.
    """

    CSS_PATH = "tcss/radio_set_changed.tcss"

    def compose(self):
        yield Button("OK", id="ok")
        yield Button("Mount modal", id="show_modal")
        yield MultipleRadioSet()

    @on(Button.Pressed, "#show_modal")
    def on_button_show_modal_pressed(self):
        self.app.push_screen(
            MultipleRadioSetModal(
                horizontal_label_set=[
                    "h_label1",
                    "h_lab2",
                    "h_long_label3\n_long_label3----\n_long_label3",
                    "4",
                    "h_label5",
                    "h_label5",
                    "4",
                    "h_label5",
                    "h_label5",
                    "h_label5",
                ],
                vertical_label_set=["v_label1", "v_long_label2", "v_label3", "v_label4", "v_label222222222222222224"],
            )
        )

    @on(Button.Pressed, "#ok")
    def on_button_pressed(self):
        selections = self.query_one(MultipleRadioSet).get_selections()
        print(selections)
