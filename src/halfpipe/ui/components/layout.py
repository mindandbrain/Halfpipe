# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import curses
from typing import TYPE_CHECKING

from .app import App
from .keyboard import Keyboard

if TYPE_CHECKING:
    from .view import View

base_pad_width = 1024


class Layout:
    def __init__(self, app: App) -> None:
        self.app = app

        color = app.color
        if color is None:
            raise ValueError("Color is not initialized")
        self.color = color

        keyboard = app.keyboard
        if keyboard is None:
            raise ValueError("Keyboard is not initialized")
        self.keyboard: Keyboard = keyboard

        self.views_by_id: dict[int, "View"] = dict()
        self.view_order: list[int] = list()
        self.view_sizes_by_id: dict[int, int] = dict()
        self.focused_view: "View | None" = None

        self.viewport_min = 0

        self.window: "curses._CursesWindow" = curses.newpad(16384, base_pad_width)
        self.window.leaveok(False)

        self.status_bar = curses.newpad(1, base_pad_width)
        self.status_bar.bkgd(" ", self.color.white)

        self.draw()

    def append(self, view: "View"):
        id = view.id
        self.views_by_id[id] = view
        self.view_sizes_by_id[id] = 0
        self.view_order.append(id)
        view._layout = self
        self.focused_view = view
        return view  # for chaining

    def remove(self, view: "View") -> "View":
        view.erase()
        id = view.id
        if id in self.views_by_id:
            del self.views_by_id[id]
        if id in self.view_sizes_by_id:
            del self.view_sizes_by_id[id]
        try:
            self.view_order.remove(id)
        except ValueError:
            pass
        if self.focused_view == view:
            self.focused_view = None
        return view  # for chaining

    def focus(self, view: "View") -> None:
        self.focused_view = view

    def _calc_viewport(self, viewport_size: int) -> None:
        if self.focused_view is None:
            return

        view_size = self.get_view_size(self.focused_view)
        view_min = self.offset(self.focused_view)
        if view_size is None or view_min is None:
            return
        if view_min < self.viewport_min:
            self.viewport_min = view_min
            return
        view_max = view_min + view_size
        viewport_max = self.viewport_min + viewport_size
        if view_max > viewport_max:
            self.viewport_min += view_max - viewport_max

    def get_layout_size(self) -> tuple[int, int]:
        y, x = self.app.screen.getmaxyx()
        return (y - 1, x - 1)

    def draw(self) -> None:
        y, x = self.get_layout_size()
        self._calc_viewport(y - 1)
        self.window.noutrefresh(self.viewport_min, 0, 0, 0, y - 2, x)
        try:
            self.status_bar.noutrefresh(0, 0, y, 0, y, x)
        except Exception:
            pass
        curses.doupdate()

    def get_view_size(self, view: "View") -> int | None:
        if view.id in self.view_sizes_by_id:
            return self.view_sizes_by_id[view.id]
        return None

    def set_view_size(self, view: "View", new_size: int) -> None:
        if view.id not in self.view_sizes_by_id or new_size is None:
            return
        if self.view_sizes_by_id[view.id] != new_size:
            self.view_sizes_by_id[view.id] = new_size
            index = self.view_order.index(view.id)
            for dependent_view_id in self.view_order[index + 1 :]:
                self.views_by_id[dependent_view_id].draw()

    def offset(self, view: "View") -> int | None:
        try:
            index = self.view_order.index(view.id)
            return sum([self.view_sizes_by_id[id] for id in self.view_order[:index]])
        except ValueError:
            return None

    def clear_status_bar(self) -> None:
        self.status_bar.erase()

    def set_status_bar(self, text: str) -> None:
        self.clear_status_bar()
        self.status_bar.addstr(0, 0, text, self.color.white)
