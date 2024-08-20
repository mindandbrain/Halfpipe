# -*- coding: utf-8 -*-

import copy
import sys

sys.path.append("/home/tomas/github/HALFpipe/src/")

from dataclasses import dataclass

from rich.cells import get_character_cell_size
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Input

from halfpipe.tui.utils.select_or_input_path import MyStatic, SelectCurrentWithInput, SelectOrInputPath, SelectOverlay


def merge_overlapping_tuples(tuples):
    """
    This function is to merge overlapping highlighted parts of the string. For example, a highlight (3,5) exists
    and we make a new highlight (6,8), thus they will be merged to just one tuple (3,8).
    """
    # Sort the list of tuples by the start position
    sorted_tuples = sorted(tuples, key=lambda x: x[0])

    merged: list = []
    for current in sorted_tuples:
        if not merged:
            merged.append(current)
        else:
            # Compare the current tuple with the last tuple in the merged list
            last = merged[-1]
            if current[0] <= last[1]:  # Check for overlap
                # Merge the two tuples: take the min start, max end, and keep the color
                merged[-1] = (min(last[0], current[0]), max(last[1], current[1]), last[2])
            else:
                merged.append(current)

    return merged


def generate_strings(base_string, schema_entities_and_colors_dict):
    """Generate pattern suggestions"""
    schema_entities = schema_entities_and_colors_dict.keys()

    import re  # Regular expressions for matching patterns in strings

    # Split the string at '{' but keep the delimiter to handle it in the loop
    parts = re.split(r"(\{)", base_string)
    result_strings = {}
    # skip_next = False  # Flag to skip next part if it is a known entity
    #
    # Rebuild the string with entities inserted appropriately
    for i in range(len(parts)):
        part = parts[i]
        if part == "{":
            # Check if the next part is a recognized entity
            if i + 1 < len(parts) and any(parts[i + 1].startswith(entity + "}") for entity in schema_entities):
                # If next part is a recognized entity, skip processing
                continue
            else:
                # Otherwise, insert each entity in new strings
                #   new_parts = parts[:i]  # Copy parts before the '{'
                for entity in schema_entities:
                    # Create a new string for each entity
                    text = Text()
                    text.append("".join(parts[:i]))  # Append the parts before '{'
                    # Append the entity with styling
                    text.append("{" + entity + "}", style="on " + schema_entities_and_colors_dict[entity])
                    text.append("".join(parts[i + 1 :]))  # Append the parts after '{entity}'

                    result_strings[entity] = text
                break  # Stop processing after handling the first '{' that can be modified
    # If no insertions were made (no suitable '{' was found), return the original string
    return result_strings if result_strings else None


class SegmentHighlighting(Input):
    """Subclass of Input that supports string highlighting."""

    # expand super class bindings, shift + left/right arrow, highlights
    Input.BINDINGS += [
        Binding("shift+left", "cursor_left_highlight", "cursor_highlight", show=False),
        Binding("shift+right", "cursor_right_highlight", "cursor_highlight", show=False),
    ]

    def highlighting(self, text, current_highlights):
        """Highlighting function, needs to be defined before init."""
        for s, e, style in sorted(current_highlights, key=lambda x: x[0]):
            text.stylize(style, s, e)
        return text

    def __init__(
        self,
        path: str,
        colors_and_labels: dict,
        *args,
        **kwargs,
    ):
        super().__init__(*args, value=path, highlighter=self.highlighting, **kwargs)  #
        self.colors_and_labels = colors_and_labels
        self.highlight_start_position: None | int = None
        # Flag to indicate whether the widget is in highlighting mode.
        self.is_highlighting = False
        # List to store highlight ranges (start, end) and their colors.
        self.previous_highlights: list = []
        self.current_highlights: list = []
        self.highlight_start_direction: None | int = None
        self.highlight_color = list(self.colors_and_labels.keys())[0]  # Default highlight color, start with the first one
        self.mouse_at_drag_start: Offset | None = None
        self.old_drag = -999
        self.highlighting_with_mouse = False
        # copy this here, so that once we hit the reset button we get it back
        self.original_value = path

    def update_colors_and_labels(self, new_colors_and_labels):
        self.colors_and_labels = new_colors_and_labels

    @property
    def _value(self) -> Text:
        """Value rendered as text."""
        if self.password:
            return Text("•" * len(self.value), no_wrap=True, overflow="ignore")
        else:
            text = Text(self.value, no_wrap=True, overflow="ignore")
            if self.highlighter is not None:
                text = self.highlighter(text, self.current_highlights)
            return text

    def action_cursor_left(self) -> None:
        """Move the cursor one position to the left."""
        self.cursor_position -= 1
        if self.is_highlighting:
            self._stop_highlighting()

    def action_cursor_right(self) -> None:
        """Accept an auto-completion or move the cursor one position to the right."""
        if self._cursor_at_end and self._suggestion:
            self.value = self._suggestion
            self.cursor_position = len(self.value)
        else:
            self.cursor_position += 1
        if self.is_highlighting:
            self._stop_highlighting()

    def action_cursor_left_highlight(self) -> None:
        """Move the cursor one position to the left."""
        self.cursor_position -= 1
        self._start_highlighting(-1)

    def action_cursor_right_highlight(self) -> None:
        """Move the cursor one position to the left."""
        self.cursor_position += 1
        self._start_highlighting(+1)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Similar to on_mouse_click, mouse button is down, prepare for highlighting."""
        offset = event.get_content_offset(self)
        if offset is None:
            return
        event.stop()
        click_x = offset.x + self.view_position

        # mouse position
        self.mouse_at_drag_start = event.screen_offset
        # cursor position
        self.offset_at_drag_start = Offset(click_x, 0)

        cell_offset = 0
        _cell_size = get_character_cell_size
        for index, char in enumerate(self.value):
            cell_width = _cell_size(char)
            if cell_offset <= click_x < (cell_offset + cell_width):
                self.cursor_position = index
                break
            cell_offset += cell_width
        else:
            self.cursor_position = len(self.value)
        self.highlight_start_position = self.cursor_position
        self.capture_mouse()
        self.can_focus = False
        self.highlighting_with_mouse = True

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Here the highlighting is happening."""
        if self.mouse_at_drag_start is not None:
            self.cursor_position = self.offset_at_drag_start.x + event.screen_x - self.mouse_at_drag_start.x
            # position of the modal at the drag start + current mouse position - mouse position at drag start
            new_drag = self.offset_at_drag_start.x + event.screen_x - self.mouse_at_drag_start.x
            if self.old_drag != new_drag:
                move_direction = new_drag - self.old_drag
                self._start_highlighting(move_direction)
            self.old_drag = new_drag

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the user releases the mouse button. Set all values to defaults."""
        self.mouse_at_drag_start = None
        self.release_mouse()
        self._stop_highlighting()
        self.can_focus = True
        self.highlighting_with_mouse = False
        self.old_drag = -999

    def _start_highlighting(self, direction) -> None:
        # If in highlighting mode, update the dynamic highlight based on the new cursor position.
        self.is_highlighting = True
        # without the highlight_start_direction variable, when user starts highlighting and
        # schange direction, highlight looses one element
        if self.highlight_start_direction is None:  # User started to hold shift key here
            self.highlight_start_direction = direction
        for h in self.previous_highlights:
            # cursor is within existing highlight, remove it then
            if self.cursor_position >= h[0] and self.cursor_position < h[1]:
                self.previous_highlights.remove(h)
                break
        if self.highlight_start_position is None:
            self.highlight_start_position = self.cursor_position - direction
        start, end = sorted([self.highlight_start_position, self.cursor_position])
        # delete current highlights since we are going to update it, what what previously
        # already highlighted is backed up in previous_highlights
        self.current_highlights = []
        if self.highlighting_with_mouse:
            if self.highlight_start_direction < 0:
                self._apend_highlight(start + 1, end, "on " + self.highlight_color)
            if self.highlight_start_direction > 0:
                self._apend_highlight(start, end + 1, "on " + self.highlight_color)
        else:
            # if started from right to left always do this
            if self.highlight_start_direction < 0:
                self._apend_highlight(start + 1, end + 1, "on " + self.highlight_color)
            # if started from left to right always do this
            if self.highlight_start_direction > 0:
                self._apend_highlight(start, end, "on " + self.highlight_color)
        self.refresh()

    def _apend_highlight(self, start: int, end: int, color: str):
        # Append the new highlight range and its color to the highlights list.
        self.current_highlights.append((start, end, color))
        if self.previous_highlights != []:
            self.current_highlights += self.previous_highlights
        self.current_highlights = merge_overlapping_tuples(self.current_highlights)

    def _stop_highlighting(self):
        self.previous_highlights = copy.deepcopy(self.current_highlights)
        self.highlight_start_position = None
        self.highlight_start_direction = None
        self.is_highlighting = False

    def reset_highlights(self):
        # clear all highlights
        self.previous_highlights.clear()
        self.current_highlights.clear()
        self.refresh()

    def reset_all(self):
        # clear all highlights
        self.previous_highlights.clear()
        self.current_highlights.clear()
        self.value = self.original_value
        self.refresh()

    def submit_path(self):
        start_offset = 0
        end_offset = 0
        highlights = copy.deepcopy(self.current_highlights)
        # self.original_value = self.value
        self.reset_highlights()
        for start, end, color in sorted(highlights, reverse=False, key=lambda x: x[0]):
            print("cccccccccccccccccc22222222222", self.colors_and_labels)
            label = self.colors_and_labels[color[3:]]
            # calculate by how much longer/shorter is the replacement string, this varies from label to label
            extra = len(label) + 2 - (end - start)
            self.value = self.value[: start + start_offset] + "{" + label + "}" + self.value[end + end_offset :]
            end_offset += extra
            self._apend_highlight(start + start_offset, end + end_offset, color)
            start_offset += extra
        # self.current_highlights is set to [] when new highlight session starts, existing highlights are thus copied to
        # self.previous_highlights
        self.previous_highlights = copy.deepcopy(self.current_highlights)
        self.post_message(self.Submitted(self.value))
        self.refresh()

    @dataclass
    class Submitted(Message):
        """Used when a submit button is pressed."""

        value: str

    class Toggle(Message):
        """Request toggle overlay."""

    async def _on_click(self, event: events.Click) -> None:
        """Inform ancestor we want to toggle."""
        self.post_message(self.Toggle())


class SelectCurrentWithInputAndSegmentHighlighting(SelectCurrentWithInput):
    def compose(self) -> ComposeResult:
        self.highlight_colors = ["red", "green", "blue", "yellow", "magenta"]
        self.labels = ["subject", "Session", "Run", "Acquisition", "task"]
        colors_and_labels = dict(zip(self.highlight_colors, self.labels, strict=False))
        # Need to change MyInput for SegmentHighlighting(Input) because both are subclass of Input
        # SegmentHighlighting(Input) and has this _apend_highlight
        yield HorizontalScroll(
            SegmentHighlighting(
                name="select_input",
                placeholder=self.placeholder,
                path=self.placeholder,
                colors_and_labels=colors_and_labels,
                id="input_prompt",
            ),
            id="input_prompt_horizontal_scroll",
        )
        yield MyStatic("▼", classes="arrow down-arrow")
        yield MyStatic("▲", classes="arrow up-arrow")

    def update_colors_and_labels(self, new_colors_and_labels):
        self.get_widget_by_id("input_prompt").update_colors_and_labels(new_colors_and_labels)


class InputWithColoredSuggestions(SelectOrInputPath):
    # Switches the Input class, in the standard one, there is MyInput(Input)
    input_class = SelectCurrentWithInputAndSegmentHighlighting

    def __init__(self, options, *, prompt_default: str = "", top_parent=None, colors_and_labels=None, id=None, classes=None):
        # pass default as prompt to super since this will be used as an fixed option in the optionlist
        super().__init__(options=options, prompt_default=prompt_default, id=id, classes=classes)
        self.colors_and_labels = colors_and_labels

    def on_mount(self):
        self.input_class.get_widget_by_id(self, id="input_prompt").update_colors_and_labels(self.colors_and_labels)

    @on(input_class.PromptChanged)
    def _select_current_with_input_prompt_changed(self, event: SelectCurrentWithInput.PromptChanged):
        def reverse_dict(original_dict):
            reversed_dict = {}
            for key, value in original_dict.items():
                reversed_dict[value] = key
            return reversed_dict

        # reversing the dictionary makes the code cleaner here
        self.labels_colors_dict = reverse_dict(self.colors_and_labels)
        path = event.value
        sugestion_strings = generate_strings(path, self.labels_colors_dict)
        if sugestion_strings is not None:
            # We do not want to show the whole path with the suggestions, but only the last part
            # We find the index of the string break using these two lines.
            color_start = sugestion_strings["subject"].spans[0].start
            last_path_break = [i for i, j in enumerate(sugestion_strings["subject"].plain[:color_start]) if j == "/"][-1] + 1
            # Remember how many characters are missing due to the now showing the whole string. This is then used to offset
            # the highlights correctly once the prompt is updated.
            self.missing_offset = last_path_break
            self.expanded = True
            self._setup_variables_for_options(
                [(sugestion_strings[f][last_path_break:], sugestion_strings[f].plain) for f in sugestion_strings.keys()]
            )
            self._setup_options_renderables()
        else:
            last_path_break = 0
            self.missing_offset = 0
            self.expanded = False
        self.post_message(self.PromptChanged(path))

    @on(SelectOverlay.UpdateSelection)
    def _update_selection(self, event: SelectOverlay.UpdateSelection) -> None:
        """Update the current selection."""
        event.stop()
        value = self._options[event.option_index][1]
        formatted_value = self._options[event.option_index][0]
        # Here the highlights are offset by the number of characters cutout from the option selection due to the fact
        # that we do not want to show the whole path with the suggestions, but only the last important part.
        self.input_class.get_widget_by_id(self, id="input_prompt")._apend_highlight(
            formatted_value.spans[0].start + self.missing_offset,
            formatted_value.spans[0].end + self.missing_offset,
            formatted_value.spans[0].style,
        )
        if value != self.value:
            self.value = value
            self.post_message(self.Changed(self, value))

        async def update_focus() -> None:
            """Update focus and reset overlay."""
            self.focus()
            self.expanded = False

        self.call_after_refresh(update_focus)  # Prevents a little flicker