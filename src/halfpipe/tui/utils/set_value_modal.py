# -*- coding: utf-8 -*-


from textual import on
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ..utils.draggable_modal_screen import DraggableModalScreen


class SetValueModal(DraggableModalScreen):
    """
    SetValueModal class representing a modal screen for setting a value.

    Parameters
    ----------
    instructions : str, optional
        Instructions to be displayed at the top of the modal (default is "Set value").
    left_button_text : str, optional
        Text for the left button (default is "Ok").
    right_button_text : str, optional
        Text for the right button (default is "Cancel").
    left_button_variant : str, optional
        Variant type for the left button (default is "success").
    right_button_variant : str, optional
        Variant type for the right button (default is "error").
    title : str, optional
        Title for the modal (default is an empty string).
    id : str or None, optional
        An optional ID for the modal (default is None).
    classes : str or None, optional
        An optional string of classes for the modal (default is None).

    Methods
    -------
    on_mount()
        Method to mount the content of the modal which includes instructions, an input field, and two action buttons.
    _on_ok_button_pressed()
        Method to handle the event of the OK button being pressed. Dismisses the modal with the input value if not empty,
        otherwise dismisses with "0".
    _on_cancel_button_pressed()
        Method to handle the event of the Cancel button being pressed. Dismisses the modal with value None.
    """

    CSS_PATH = ["tcss/set_value_modal.tcss"]

    def __init__(
        self,
        instructions="Set value",
        left_button_text="Ok",
        right_button_text="Cancel",
        left_button_variant="success",
        right_button_variant="error",
        title="",
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.instructions = instructions
        self.left_button_text = left_button_text
        self.right_button_text = right_button_text
        self.left_button_variant = left_button_variant
        self.right_button_variant = right_button_variant

        self.title_bar.title = title

    def on_mount(self) -> None:
        self.content.mount(
            Static(self.instructions),
            Input(""),
            Horizontal(
                Button(self.left_button_text, variant=self.left_button_variant, classes="button ok"),
                Button(self.right_button_text, variant=self.right_button_variant, classes="button cancel"),
                classes="button_grid",
            ),
        )

    @on(Button.Pressed, ".ok")
    def _on_ok_button_pressed(self):
        input_widget = self.query_one(Input)
        if input_widget.value == "":
            self.dismiss("0")
        else:
            self.dismiss(input_widget.value)

    @on(Button.Pressed, ".cancel")
    def _on_cancel_button_pressed(self):
        self.dismiss(None)
