# -*- coding: utf-8 -*-

import sys

sys.path.append("/home/tomas/github/HALFpipe/src/")


from dataclasses import dataclass

from inflection import humanize
from rich.text import Text
from textual import on, work
from textual.containers import Horizontal, HorizontalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerState

from halfpipe.tui.utils.list_of_files_modal import ListOfFiles
from halfpipe.tui.utils.path_pattern_builder import PathPatternBuilder, evaluate_files

from ..utils.confirm_screen import SimpleMessageModal
from ..utils.context import ctx


class FileItem(Widget):
    success_value: reactive[bool] = reactive(None, init=False)

    @dataclass
    class IsDeleted(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class SuccessChanged(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class PathPatternChanged(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    @dataclass
    class IsFinished(Message):
        file_item: "FileItem"
        value: str

        @property
        def control(self):
            """Alias for self.file_browser."""
            return self.file_item

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
        delete_button=True,
        title="",
        pattern_class=None,
        id_key="",
        load_object=None,
        callback_message=None,
        message_dict=None,
        **kwargs,
    ) -> None:
        """ """
        super().__init__(id=id, classes=classes, **kwargs)
        # dictionary for results from the PathPatternBuilder
        #    self.pattern_match_results =
        self.delete_button = delete_button
        self.pattern_class = None if pattern_class is None else pattern_class
        self.title = "Not implemented yet"
        if self.pattern_class is not None:
            self.title = self.pattern_class.header_str
            # print(
            #     "FileItem ssssssssssssssssssssssssssssssssssssssssssssssssssss",
            #     self.pattern_class.get_entities,
            #     self.pattern_class.get_entity_colors_list,
            #     self.pattern_class.get_required_entities,
            # )
            # print("FileItem aaaaaaaaaaaaaaaa", pattern_class.header_str)
            if self.pattern_class.next_step_type is not None:
                # print("hhhhhhhhhhhhhhhhhhhhhhhhhhhas nextt steppp")
                self.pattern_class.callback = self.callback_func
            self.pattern_class.id_key = id

        self.load_object = load_object
        self.border_title = "id: " + str(id)
        self.from_edit = False
        # self.callback_message = callback_message
        print("ccccccccccccccccccccccccccccccccc init self.callback_message", callback_message)
        #
        # self.callback_message = callback_message
        #
        if message_dict is not None and callback_message is None:
            self.callback_message = self.prettify_message_dict(message_dict)
        else:
            self.callback_message = callback_message

        self.pattern_match_results = {"file_pattern": "", "message": "Found 0 files.", "files": []}
        print("2ccccccccccccccccccccccccccccccccc init self.callback_message", self.callback_message)

    def prettify_message_dict(self, message_dict):
        info_string = Text("")
        for key in message_dict:
            # if there is only one item, we do not separate items on new lines
            if len(message_dict[key]) <= 1:
                sep_char = ""
                separ_line = "-" * (len(key) + len(message_dict[key]) + 3)
            else:
                sep_char = "\n"
                separ_line = "-" * (max([len(s) for s in [key] + message_dict[key]]) + 3)
            message_value = ""
            for message in message_dict[key]:
                message_value += message + " " if message.endswith("\n") else message + "\n"
            info_string += Text(humanize(key) + ": " + sep_char, style="bold green") + Text(
                message_value + separ_line, style="white"
            )
        return info_string

    def callback_func(self, message_dict):
        self.callback_message = self.prettify_message_dict(message_dict)

    def compose(self):
        # print("11111111111111111111111 compose")
        yield HorizontalScroll(Static("Edit to enter the file pattern", id="static_file_pattern"))
        with Horizontal(id="icon_buttons_container"):
            yield Button(" ℹ", id="info_button", classes="icon_buttons")

            yield Button("🖌", id="edit_button", classes="icon_buttons")
            yield Button("👁", id="show_button", classes="icon_buttons")
            if self.delete_button:
                yield Button("❌", id="delete_button", classes="icon_buttons")

    def on_mount(self) -> None:
        # print("mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmount 222")
        # print("----------self.load_object self.load_object self.load_object ------------", self.load_object)

        if self.load_object is None:
            self.get_widget_by_id("edit_button").tooltip = "Edit"
            if self.delete_button:
                self.get_widget_by_id("delete_button").tooltip = "Delete"
            self.app.push_screen(
                PathPatternBuilder(
                    #  path="/home/tomas/github/ds002785_v2/sub-0001/func/sub-0001_task-emomatching_acq-seq_bold.nii.gz",
                    #  path="/home/tomas/github/ds005115/sub-01/ses-01/fmap/sub-01_ses-01_phasediff.nii.gz",
                    path="/home/tomas/github/ds005115/sub-01/ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz",
                    title=self.title,
                    highlight_colors=self.pattern_class.get_entity_colors_list,
                    labels=self.pattern_class.get_entities,
                ),
                self._update_file_pattern,
            )
        else:
            if isinstance(self.load_object, dict):
                # print("isinstance(self.load_object, dict) dddddddddddddddddddddddddddd loadobject dict", self.load_object)
                self._update_file_pattern(self.load_object)
            else:
                pattern_load = {}
                pattern_load["file_pattern"] = self.load_object.path
                message, filepaths = evaluate_files(self.load_object.path.replace("{sub}", "{subject}"))
                # print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa message, filepathsmessage, filepaths", message, filepaths)
                pattern_load["message"] = message
                pattern_load["files"] = filepaths
                # self.callback_message = self.load_object.metadata
                # print("dddddddddddddddddddddddddor self.load_object", dir(self.load_object))
                self._update_file_pattern(pattern_load)
        if (self.pattern_class and self.pattern_class.callback) or self.callback_message:
            print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa self.callback_message :::", self.callback_message)
            self.get_widget_by_id("info_button").styles.visibility = "visible"
        else:
            self.get_widget_by_id("info_button").remove()

    @on(Button.Pressed, "#edit_button")
    def _on_edit_button_pressed(self):
        """
        Opens modal for selecting the search file pattern.
        The results from this modal goes then to _update_file_pattern function.
        """
        self.from_edit = True
        self.app.push_screen(
            PathPatternBuilder(
                # path="/home/tomas/github/ds002785_v2/sub-0001/func/sub-0001_task-emomatching_acq-seq_bold.nii.gz",
                path="/home/tomas/github/ds005115/sub-01/ses-01/fmap/sub-01_ses-01_phasediff.nii.gz",
                # path="/home/tomas/github/ds005115/sub-01/ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz",
                title=self.title,
            ),
            self._update_file_pattern,
        )

    @property
    def get_pattern_match_results(self):
        return self.pattern_match_results

    @property
    def get_callback_message(self):
        return self.callback_message

    # runs after the PathPatternBuilder modal
    @work(exclusive=True, name="update_worker")
    async def _update_file_pattern(self, pattern_match_results):
        """Update various variables based on the results from the PathPatternBuilder"""
        if pattern_match_results is not False:
            self.pattern_match_results = pattern_match_results
            # self.post_message(self.PathPatternChanged(self, self.pattern_match_results))

            # Update the static label using the file pattern.
            self.get_widget_by_id("static_file_pattern").update(pattern_match_results["file_pattern"])
            # Tooltip telling us how many files were  found.
            self.get_widget_by_id("show_button").tooltip = pattern_match_results["message"]
            # If 0 files were found, the border is red, otherwise green.
            if len(pattern_match_results["files"]) > 0:
                self.styles.border = ("solid", "green")
                self.success_value = True
            else:
                self.styles.border = ("solid", "red")
                self.success_value = False

            # try to push to ctx
            # print("iiiiiiiiiiiiiiiiiiiiiiiiii", pattern_match_results["file_pattern"])
            # obj = AnatStep(ctx=self.app.ctx, path=pattern_match_results["file_pattern"].plain)
            # obj.setup()
            # fix this because sometimes this can be just ordinary string
            if len(pattern_match_results["files"]) > 0:
                #  try:
                if self.pattern_class is not None:
                    await self.execute_class()
                    # if isinstance(pattern_match_results["file_pattern"], str):
                    #     self.pattern_class.push_path_to_context_obj(path=pattern_match_results["file_pattern"])
                    # else:
                    #     self.pattern_class.push_path_to_context_obj(path=pattern_match_results["file_pattern"].plain)
            # print('rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr returned_value', returned_value)
            # except:
            #    print("bbbbbbbbbbla")

            if self.from_edit:
                await self.update_all_duplicates()
        #    self.update_all_duplicates()

        else:
            # delete it self if cancelled and was not existing before
            if self.pattern_match_results["file_pattern"] == "":
                self.remove_all_duplicates()
                self.remove()

    # @work(exclusive=True, name="step_worker")
    async def execute_class(self):
        if self.pattern_class is not None:
            if isinstance(self.pattern_match_results["file_pattern"], str):
                await self.pattern_class.push_path_to_context_obj(path=self.pattern_match_results["file_pattern"])
                print("vrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr", self.pattern_class.callback)
            else:
                await self.pattern_class.push_path_to_context_obj(path=self.pattern_match_results["file_pattern"].plain)
                print("2vrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr", self.pattern_class.callback)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        # print("test", event.handler_name)
        # print("test", event.namespace)
        # print("test", event.worker.name)
        # print("test", event.state)
        # if event.worker.name == 'step_worker':
        #     if event.state == WorkerState.SUCCESS:
        #         print("i am finished with the taaaaaaaaaaask", self.get_callback_message)
        #         self.post_message(self.IsFinished(self, self.pattern_match_results))
        if event.worker.name == "update_worker":
            if event.state == WorkerState.SUCCESS:
                print("cccccccccccccccccccccccccccccccccall back heeeeeeeeeeeeeeere????", self.get_callback_message)
                self.pattern_match_results["callback_message"] = self.get_callback_message
                self.post_message(self.PathPatternChanged(self, self.pattern_match_results))

    @on(Button.Pressed, "#delete_button")
    def _on_delete_button_pressed(self):
        """Remove the file pattern item."""
        # Creation of the FileItem does not automatically imply creation in the cache.
        # For this a pattern needs to be created. By cancelling the modal, the widget is created but the filepattern is not.
        if self.id in ctx.cache:
            ctx.cache.pop(self.id)
        self.remove_all_duplicates()
        print("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        # self.delete_value = True
        self.post_message(self.IsDeleted(self, "yes"))
        # await self.remove()

    # async def watch_delete_value(self) -> None:
    #     self.post_message(self.IsDeleted(self, self.delete_value))

    @on(Button.Pressed, "#show_button")
    def _on_show_button_pressed(self):
        """Shows a modal with the list of files found using the given pattern."""
        self.app.push_screen(ListOfFiles(self.pattern_match_results))

    @on(Button.Pressed, "#info_button")
    def _on_info_button_pressed(self):
        """Shows a modal with the list of files found using the given pattern."""
        # print("iiiiiiiiiiiiiiiiiiiiiiiiiiiiiii", self.callback_message)
        self.app.push_screen(SimpleMessageModal(self.callback_message, title="Meta information"))

    # def watch_success_value(self) -> None:
    #     self.post_message(self.SuccessChanged(self, self.success_value))

    # def watch_pattern_match_results(self) -> None:
    #     self.post_message(self.PathPatternChanged(self, self.pattern_match_results))

    def remove_all_duplicates(self):
        for w in self.app.walk_children(FileItem):
            # print("remove_all_duplicates w.idw.idw.idw.idw.idw.idw.idw.idw.id", w.id)
            # remove itself standardly later
            if w.id == self.id and w != self:
                w.remove()

    async def update_all_duplicates(self):
        for w in self.app.walk_children(FileItem):
            # print("update_all_duplicates w.idw.idw.idw.idw.idw.idw.idw.idw.id", w.id)
            # remove itself standardly later
            if w.id == self.id and w != self:
                if w.pattern_match_results != self.pattern_match_results:
                    await w._update_file_pattern(self.pattern_match_results)
        self.from_edit = False


# class Main(App):
#     CSS_PATH = ["./tcss/path_segment_highlighter2.tcss"]
#
#     def compose(self):
#         with VerticalScroll(id="test_container"):
#             yield Button("Add", id="add_button")
#
#     def on_mount(self) -> None:
#         self.get_widget_by_id("add_button").tooltip = "Add new file pattern"
#
#     @on(Button.Pressed, "#add_button")
#     def _add_file_time(self):
#         self.get_widget_by_id("test_container").mount(FileItem(classes="file_patterns"))
#         self.refresh()
#
#
# if __name__ == "__main__":
#     app = Main()
#     app.run()
