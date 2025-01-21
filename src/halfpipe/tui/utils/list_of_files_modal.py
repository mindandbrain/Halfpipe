# -*- coding: utf-8 -*-

from textual import on
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import Button, Static

from .draggable_modal_screen import DraggableModalScreen


class ListOfFiles(DraggableModalScreen):
    """
    ListOfFiles

    A class that represents a modal screen displaying a list of files that match a certain pattern.

    Parameters
    ----------
    pattern_match_results : dict
        A dictionary containing the pattern match results with keys 'message' and 'files'.
    **kwargs : dict
        Additional keyword arguments passed to the parent class.

    Methods
    -------
    on_mount()
        Invoked when the screen is mounted. It mounts a message, a scrollable list of files, and a close button.

    _on_close_button_pressed()
        Handles the event when the close button is pressed. It removes the modal screen from the view.
    """

    def __init__(self, pattern_match_results, **kwargs) -> None:
        super().__init__(**kwargs)
        self.pattern_match_results = pattern_match_results
        self.title_bar.title = "List of matching files"

    def on_mount(self) -> None:
        self.content.mount(
            Static(self.pattern_match_results["message"], id="message"),
            # ScrollableContainer(Static('\n'.join(self.pattern_match_results["files"])))),
            ScrollableContainer(Static("\n".join(sorted(self.pattern_match_results["files"])), id="file_list")),
            Horizontal(Button("Close", id="close_button"), id="close_button_container"),
        )

    @on(Button.Pressed, "#close_button")
    def _on_close_button_pressed(self):
        self.app.pop_screen()
