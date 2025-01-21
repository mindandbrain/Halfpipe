# -*- coding: utf-8 -*-
from textual import on
from textual.containers import Horizontal
from textual.widgets import Button, Static

from .draggable_modal_screen import DraggableModalScreen


class Confirm(DraggableModalScreen):
    """
    Confirm(DraggableModalScreen)

    A modal dialog window that prompts the user with a message and two buttons ("Ok" and "Cancel").
    It allows customization of the button texts, button variants, and the message content.

    Attributes
    ----------
    CSS_PATH : list of str
        Path to the CSS file for styling the modal.

    Methods
    -------
    __init__(
        self,
        text="Are you sure?",
        left_button_text="Ok",
        right_button_text="Cancel",
        left_button_variant="success",
        right_button_variant="error",
        title="",
        id: str | None = None,
        classes: str | None = None,
        width=None,
        message_widget=Static,
    ) -> None:
        Initializes the Confirm modal with provided parameters.

    on_resize()
        Adjusts the width of the message widget based on the container's size.

    on_mount()
        Mounts the message widget and buttons to the modal content.

    ok()
        Handles the event when the "Ok" button is pressed.

    cancel()
        Handles the event when the "Cancel" button is pressed.

    key_escape()
        Handles the event when the Escape key is pressed.

    _confirm_window()
        Dismisses the modal and returns True.

    _cancel_window()
        Dismisses the modal and returns False.
    """

    CSS_PATH = ["tcss/confirm.tcss"]

    def __init__(
        self,
        text="Are you sure?",
        left_button_text="Ok",
        right_button_text="Cancel",
        left_button_variant="success",
        right_button_variant="error",
        title="",
        id: str | None = None,
        classes: str | None = None,
        width=None,
        message_widget=Static,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.text = text

        self.title_bar.title = title
        self.message_widget = message_widget
        # this here allows to use the modal just with one button, either outputting True or False (left/right)
        # use button_text = False to disable the button
        active_incides = [i for i, val in enumerate([left_button_text, right_button_text]) if val is not False]
        self.active_index = None
        if len(active_incides) == 1:
            active_index = active_incides[0]
            self.active_index = active_index
            self.buttons = [
                Button(
                    [left_button_text, right_button_text][active_index],
                    variant=[left_button_variant, right_button_variant][active_index],
                    classes=["button ok", "button cancel"][active_index],
                )
            ]
        else:
            self.buttons = [
                Button(left_button_text, variant=left_button_variant, classes="button ok"),
                Button(right_button_text, variant=right_button_variant, classes="button cancel"),
            ]

    def on_resize(self):
        self.get_widget_by_id("message").styles.width = (
            self.get_widget_by_id("draggable_modal_screen_container_wrapper").container_size.width - 2
        )

    def on_mount(self) -> None:
        self.content.mount(
            self.message_widget(self.text, id="message"),
            Horizontal(
                *self.buttons,
                classes="button_grid",
            ),
        )

    @on(Button.Pressed, ".button_grid .ok")
    def ok(self):
        self._confirm_window()

    @on(Button.Pressed, ".button_grid .cancel")
    def cancel(self):
        self.request_close()

    def key_escape(self):
        self.request_close()

    def _confirm_window(self):
        self.dismiss(True)

    def request_close(self):
        # Clicking on the 'X' in the draggable window bar, escape key and the close button must always yield the same dismiss
        # value!
        if self.active_index == 0:  # default button is the 'Ok' button
            self.dismiss(True)
        else:  # default button is the 'Cancel' button or we have bot buttons
            self.dismiss(False)


class SimpleMessageModal(Confirm):
    """
    class SimpleMessageModal(Confirm):

    Represents a simple message modal dialog with a customizable message and title.

    Parameters
    ----------
    text : str
        The message to be displayed in the modal.
    title : str, optional
        The title of the modal window (default is an empty string).
    id : str or None, optional
        The unique identifier for the modal (default is None).
    classes : str or None, optional
        Additional CSS classes to apply to the modal (default is None).
    """

    def __init__(self, text, title="", id: str | None = None, classes: str | None = None) -> None:
        super().__init__(
            text=text,
            title=title,
            id=id,
            classes=classes,
            left_button_text=False,
            right_button_text="Close",
            right_button_variant="default",
            message_widget=Static,
        )
