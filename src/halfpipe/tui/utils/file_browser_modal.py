# -*- coding: utf-8 -*-


import functools
import os
from pathlib import Path
from typing import Iterable

from textual import on
from textual.containers import Horizontal
from textual.widgets import Button, DirectoryTree, Input

from .confirm_screen import Confirm
from .draggable_modal_screen import DraggableModalScreen
from .select_or_input_path import SelectOrInputPath, create_path_option_list


def path_test(path, isfile=False):
    """
    Parameters
    ----------
    path : str
        The path to the file or directory to be checked.
    isfile : bool, optional
        If True, the function expects the path to be a file. If False, it expects the path to be a directory. Default is False.

    Returns
    -------
    str
        A message indicating the result of the path check. Possible values are:
        - "OK" if the path corresponds to the expected type (file or directory) and is writable.
        - "A directory was selected instead of a file!" if isfile is True, but the path is a directory.
        - "A file was selected instead of a directory!" if isfile is False, but the path is a file.
        - "Permission denied." if the path is not writable.
        - "File not found." if the path does not exist.
    """
    if os.path.exists(path):
        if os.access(path, os.W_OK):
            if isfile:
                result_info = "OK" if os.path.isfile(path) else "A directory was selected instead of a file!"
            else:
                result_info = "OK" if os.path.isdir(path) else "A file was selected instead of a directory!"
        else:
            result_info = "Permission denied."
    else:
        result_info = "File not found."
    return result_info


# Partially apply path_test with isfile=True
path_test_with_isfile_true = functools.partial(path_test, isfile=True)


class FilteredDirectoryTree(DirectoryTree):
    """
    FilteredDirectoryTree class provides functionality to filter out hidden files and directories
    from a list of paths.

    Methods
    -------
    filter_paths(paths)
        Filters out paths that have names starting with a period, indicating hidden files or directories.

    Parameters
    ----------
    paths : Iterable[Path]
        A list of file and directory paths to filter.

    Returns
    -------
    Iterable[Path]
        A list of paths excluding those with names starting with a period.
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not path.name.startswith(".")]


class FileBrowserModal(DraggableModalScreen):
    """
    FileBrowserModal
    A class that represents a draggable modal screen for browsing directories and selecting paths.

    Attributes
    ----------
    CSS_PATH : list
        Path to the CSS file for styling the file browser.

    Methods
    -------
    __init__(title="Browse", path_test_function=None, **kwargs)
        Initializes the FileBrowserModal.

    on_mount()
        Executed when the modal is mounted. Mounts the directory tree and path input components.

    _select_or_input_path_changed(message)
        Event handler for changes in the path selection or input. Manages the expansion and collapse of directory nodes.

    on_filtered_directory_tree_directory_or_file_selected(message)
        Event handler for directory or file selection changes. Updates the selected directory and path input prompt.

    update_from_input()
        Updates the selected directory based on input value from the path input box.

    ok()
        Confirms the selected path and calls the confirm window function.

    cancel()
        Cancels the file browsing and calls the cancel window function.

    key_escape()
        Cancels the file browsing when the escape key is pressed.

    _confirm_window()
        Validates the selected path and dismisses the modal if valid, otherwise shows an error message.

    _cancel_window()
        Dismisses the modal without selecting any path.
    """

    CSS_PATH = ["tcss/file_browser.tcss"]

    def __init__(self, title="Browse", path_test_function=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.expanded_nodes: list = []
        self.title_bar.title = title
        self.path_test_function = path_test if path_test_function is None else path_test_function

    def on_mount(self) -> None:
        base = "/"
        self.content.mount(
            FilteredDirectoryTree("/", classes="browse_tree", id="dir_tree"),
            #     Input(placeholder="Set path to the " + self.path_to, id="path_input_box2"),
            SelectOrInputPath(
                [(f, f) for f in create_path_option_list(base=base, include_base=True)],
                prompt_default=base,
                top_parent=self,
                id="path_input_box2",
            ),
            Horizontal(
                Button("Ok", classes="button ok"),
                Button("Cancel", classes="button cancel"),
            ),
        )

    @on(SelectOrInputPath.PromptChanged)
    def _select_or_input_path_changed(self, message):
        path = message.value
        self.selected_directory = path
        # scan over already expanded nodes
        opened_node_paths = [str(node.data.path) + "/" for node in self.expanded_nodes]

        # collapsing nodes
        if opened_node_paths != []:
            path_of_last_expanded_node = str(self.expanded_nodes[-1].data.path)
            if path_of_last_expanded_node not in path:  # compare with the last one, the highest opened node
                self.expanded_nodes[-1].collapse()
                self.expanded_nodes.pop()

        if os.path.isdir(path) and path.endswith("/"):
            # scan the whole tree and find node with the particular path and expand it
            tree = self.get_widget_by_id("dir_tree")
            for t in tree._tree_nodes:
                tree_path = str(tree._tree_nodes[t].data.path) + "/"
                node = tree._tree_nodes[t]

                # expanding nodes, if path is in one of the nodes and it was not already expanded
                if tree_path == path and path not in opened_node_paths:
                    if not node.allow_expand:
                        return
                    node.expand()
                    self.expanded_nodes.append(node)

    @on(FilteredDirectoryTree.DirectorySelected, ".browse_tree")
    @on(FilteredDirectoryTree.FileSelected, ".browse_tree")
    async def on_filtered_directory_tree_directory_or_file_selected(self, message):
        self.selected_directory = message.path
        label = self.get_widget_by_id("path_input_box2")
        label.change_prompt_from_parrent(str(self.selected_directory))

    @on(Input.Submitted, "#path_input_box2")
    def update_from_input(self):
        self.selected_directory = self.get_widget_by_id("path_input_box2").value

    @on(Button.Pressed, ".ok")
    def ok(self):
        self._confirm_window()

    @on(Button.Pressed, ".cancel")
    def cancel(self):
        self._cancel_window()

    def key_escape(self):
        self._cancel_window()

    def _confirm_window(self):
        self.update_from_input()
        path_test_result = self.path_test_function(self.selected_directory)

        def ask_for_new_directory(value):
            def create_new_directory(value):
                if value is True:
                    os.mkdir(self.selected_directory)
                    self.dismiss(self.selected_directory)
                else:
                    pass

            self.app.push_screen(
                Confirm(
                    "Do you want to create a new directory?",
                    left_button_text="YES",
                    right_button_text="NO",
                    left_button_variant="error",
                    right_button_variant="success",
                    title="Create new directory",
                    id="new_dir",
                    classes="confirm_warning",
                ),
                create_new_directory,
            )

        if path_test_result == "OK":
            self.dismiss(self.selected_directory)
        elif path_test_result == "File not found.":
            self.app.push_screen(
                Confirm(
                    path_test_result,
                    title="Error - Invalid path",
                    left_button_text=False,
                    right_button_text="OK",
                    id="invalid_path_warning_modal",
                    classes="confirm_error",
                ),
                ask_for_new_directory,
            )
        else:
            self.app.push_screen(
                Confirm(
                    path_test_result,
                    title="Error - Invalid path",
                    left_button_text=False,
                    right_button_text="OK",
                    id="invalid_path_warning_modal",
                    classes="confirm_error",
                )
            )

    def _cancel_window(self):
        self.dismiss("")
