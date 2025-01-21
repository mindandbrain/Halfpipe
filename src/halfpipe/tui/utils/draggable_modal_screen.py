# -*- coding: utf-8 -*-
from typing import Any

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Container
from textual.geometry import Offset
from textual.reactive import var
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class WindowTitleBar(Container):
    """
    class WindowTitleBar(Container):
        A class representing a window title bar with customizable options including title, maximize, minimize,
        and close buttons.

    DEFAULT_CSS : str
        The default CSS styling for the WindowTitleBar and its child elements.

    MINIMIZE_ICON : str
        The Unicode icon representing the minimize button.

    MAXIMIZE_ICON : str
        The Unicode icon representing the maximize button.

    RESTORE_ICON : str
        The Unicode icon representing the restore button.

    CLOSE_ICON : str
        The Unicode icon representing the close button.

    title : str
        The title text displayed on the title bar.

    __init__(self, title: str = "", allow_maximize: bool = False, allow_minimize: bool = False, **kwargs: Any) -> None
        Initialize the WindowTitleBar instance with given title, maximize, and minimize options.

        Parameters
        ----------
        title : str, optional
            The title text to be displayed on the title bar. Default is an empty string.
        allow_maximize : bool, optional
            Flag to indicate whether a maximize button should be added. Default is False.
        allow_minimize : bool, optional
            Flag to indicate whether a minimize button should be added. Default is False.
        **kwargs : Any
            Additional keyword arguments.

    compose(self) -> ComposeResult
        Compose the widgets to be added to the title bar, including the title text and optional minimize, maximize, restore,
        and close buttons.

        Yields
        ------
        Static :
            A static widget containing the title text.
        Button :
            The minimize button if allowed.
        Button :
            The maximize button if allowed.
        Button :
            A hidden restore button if maximize is allowed.
        Button :
            The close button.
    """

    DEFAULT_CSS = """
        WindowTitleBar {
            layout: horizontal;
            width: auto;
            height: 3;
            background: $accent;
            color: auto;
            text-style: bold;
        }

        WindowTitleBar Button {
            max-width: 6;
            height: 3;
            padding-top: 0;
            padding-left: 0;
            background: $accent;
            border: none;
        }

        WindowTitleBar Button:hover {
            border: none;
            border-top: none;
            border-bottom: none;
            background: $accent;
            color: black;
            border: thick black;
        }

        WindowTitleBar Button:focus {
                text-style: none;
        }

        .window_title {
            width: 1fr;
            height: 100%;
            content-align: left middle;
            padding-left: 1;
        }
    """

    MINIMIZE_ICON = "🗕"
    MAXIMIZE_ICON = "🗖"
    RESTORE_ICON = "🗗"
    CLOSE_ICON = "✕"

    title = var("")

    def __init__(
        self,
        title: str = "",
        allow_maximize: bool = False,
        # allow_minimize: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a title bar."""
        super().__init__(**kwargs)
        self.title = title
        self.ALLOW_MAXIMIZE = allow_maximize
        # self.allow_minimize = allow_minimize

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        yield Static(self.title, classes="window_title")
        # if self.allow_minimize:
        #     yield Button(self.MINIMIZE_ICON, classes="window_minimize")
        if self.allow_maximize:
            yield Button(self.MAXIMIZE_ICON, classes="window_maximize")
            restore_button = Button(self.RESTORE_ICON, classes="window_restore")
            restore_button.display = False
            yield restore_button
        yield Button(self.CLOSE_ICON, classes="window_close")


class DraggableModalScreen(ModalScreen):
    """
    DraggableModalScreen is a type of ModalScreen that can be dragged around by the user using the mouse.

    DEFAULT_CSS: str
        Default CSS styling for the draggable modal screen and its container.

    __init__(id: str | None = None, classes: str | None = None) -> None
        Initializes a new DraggableModalScreen instance.

        Parameters
        ----------
        id: str | None
            The unique identifier for the modal screen.
        classes: str | None
            One or more CSS classes to apply to the modal screen.

    on_resize()
        Adjusts the width of the window title bar to match the width of the container wrapper when the screen is resized.

    compose() -> ComposeResult
        Composes the components of the modal screen.

    on_mouse_move(event: events.MouseMove) -> None
        Called when the user moves the mouse.

        Parameters
        ----------
        event: events.MouseMove
            The event object containing details about the mouse movement.

    on_mouse_down(event: events.MouseDown) -> None
        Called when the user presses the mouse button.

        Parameters
        ----------
        event: events.MouseDown
            The event object containing details about the mouse down action.

    on_mouse_up(event: events.MouseUp) -> None
        Called when the user releases the mouse button.

        Parameters
        ----------
        event: events.MouseUp
            The event object containing details about the mouse up action.

    request_close()
        Requests the modal screen to close.
    """

    DEFAULT_CSS = """
        DraggableModalScreen {
            align: center middle;
         }

        #draggable_modal_screen_container_wrapper {
            width: auto;
            height: auto;
            border-left: thick $accent;
            border-right: thick $accent;
            border-bottom: thick $accent;
        }
    """

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.title_bar = WindowTitleBar(id="window_title_bar")
        self.content = Container(self.title_bar, id="draggable_modal_screen_container_wrapper", classes="window_content")

        # mouse_at_drag_start also servers as "is dragging"
        self.mouse_at_drag_start: Offset | None = None

    def on_resize(self):
        self.get_widget_by_id("window_title_bar").styles.width = self.get_widget_by_id(
            "draggable_modal_screen_container_wrapper"
        ).container_size.width

    def compose(self) -> ComposeResult:
        yield self.content

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the user moves the mouse."""
        window = self.get_widget_by_id("draggable_modal_screen_container_wrapper")
        if self.mouse_at_drag_start is not None:
            # position of the modal at the drag start + current mouse position - mouse position at drag start
            window.styles.offset = (
                self.offset_at_drag_start.x + event.screen_x - self.mouse_at_drag_start.x,
                self.offset_at_drag_start.y + event.screen_y - self.mouse_at_drag_start.y,
            )

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the user presses the mouse button."""
        window = self.get_widget_by_id("draggable_modal_screen_container_wrapper")
        window.focus()

        # what widget is currently at the mouse coursor position and left mouse button is used
        widget, _ = self.screen.get_widget_at(*event.screen_offset)
        if widget != self.title_bar.query_one(".window_title") or event.button != 1:
            return

        # mouse position at drag start
        self.mouse_at_drag_start = event.screen_offset
        self.offset_at_drag_start = Offset(
            int(window.styles.offset.x.value),
            int(window.styles.offset.y.value),
        )
        self.capture_mouse()
        self.can_focus = False

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the user releases the mouse button."""
        self.mouse_at_drag_start = None
        self.release_mouse()
        self.can_focus = True

    @on(Button.Pressed, ".window_close")
    def windown_close(self):
        self.request_close()

    def request_close(self):
        self.dismiss(False)
