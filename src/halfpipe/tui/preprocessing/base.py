# -*- coding: utf-8 -*-
# ok to review

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Static, Switch

from ...model.file.base import File
from ..utils.context import ctx
from ..utils.custom_general_widgets import LabelledSwitch, SwitchWithInputBox, SwitchWithSelect
from ..utils.custom_switch import TextSwitch
from ..utils.draggable_modal_screen import DraggableModalScreen
from ..utils.filebrowser import FileBrowser
from ..utils.meta_data_steps import CheckBoldSliceEncodingDirectionStep


class SetInitialVolumesRemovalModal(DraggableModalScreen):
    """
    SetInitialVolumesRemovalModal class

    A draggable modal screen that allows users to set the number of initial volumes to remove.

    Methods
    -------
    __init__(**kwargs)
        Initializes the modal with a title.

    on_mount()
        Sets up the modal content including a prompt, input field, and OK/Cancel buttons.

    _on_ok_button_pressed()
        Handles the OK button press event, retrieves the input value, and dismisses the modal with the given input.

    _on_cancel_button_pressed()
        Handles the Cancel button press event and dismisses the modal with None.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_bar.title = "Remove initial volumes"

    def on_mount(self) -> None:
        self.content.mount(
            Static("Set number of how many initial volumes to remove"),
            Input(""),
            Horizontal(Button("OK", id="ok"), Button("Cancel", id="cancel")),
        )

    @on(Button.Pressed, "#ok")
    def _on_ok_button_pressed(self):
        input_widget = self.query_one(Input)
        if input_widget.value == "":
            self.dismiss("0")
        else:
            self.dismiss(input_widget.value)

    @on(Button.Pressed, "#cancel")
    def _on_cancel_button_pressed(self):
        self.dismiss(False)


class Preprocessing(Widget):
    """
    Preprocessing is a widget that handles the configuration of various preprocessing settings for neuroimaging data.

    Attributes
    ----------
    default_settings : dict
        Default settings for preprocessing operations specified in the widget.

    Methods
    -------
    __init__(id: str | None = None, classes: str | None = None) -> None
        Initializes the Preprocessing widget with optional id and class attributes.

    compose() -> ComposeResult
        Constructs and arranges the different interactive components within the widget.

    _on_via_algorithm_switch_changed(self, message)
        Event handler for changes in the "via_algorithm_switch".

    on_run_reconall_switch_changed(self, message: Message)
        Event handler for changes in the "run_reconall" switch.

    on_time_slicing_switch_changed(self, message: Message)
        Asynchronous event handler for changes in the "time_slicing_switch".

    callback_func(self, message_dict: dict)
        Callback function to handle messages from the FilePattern or CheckMetaData classes.
    """

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        # To overriding the default settings is done only when loading from a spec file. To do this, this attribute needs
        # firstly to be redefined and then the widget recomposed as is done in the working_directory widget.
        self.default_settings = {"run_reconall": False, "slice_timing": False, "via_algorithm_switch": False, "dummy_scans": 0}

    def compose(self) -> ComposeResult:
        # Widgets for settings that go to the json files
        anatomical_settings_panel = Container(
            Horizontal(
                Static("Run recon all", classes="description_labels"),
                TextSwitch(value=self.default_settings["run_reconall"], id="run_reconall"),
            ),
            id="anatomical_settings",
            classes="components",
        )
        slice_timming_info_panel = Static("", id="slice_timming_info")
        slice_timing_panel = Container(
            Horizontal(
                Static("Turn on slice timing", classes="description_labels"),
                TextSwitch(value=self.default_settings["slice_timing"], id="time_slicing_switch"),
            ),
            slice_timming_info_panel,
            id="slice_timing",
            classes="components",
        )
        remove_initial_volumes_panel = Vertical(
            Horizontal(
                Static("Detect non-steady-state via algorithm", classes="description_labels"),
                TextSwitch(False if self.default_settings["dummy_scans"] is not None else True, id="via_algorithm_switch"),
            ),
            Horizontal(
                Static(
                    "Remove initial volumes from scans",
                    id="manualy_set_volumes_to_remove_label",
                    classes="description_labels",
                ),
                Static(str(self.default_settings["dummy_scans"]), id="remove_volumes_value"),
                Button("🖌", id="edit_button", classes="icon_buttons"),
                id="manualy_set_volumes_to_remove",
            ),
            id="remove_initial_volumes",
            classes="components",
        )
        functional_settings_panel = Container(
            slice_timing_panel,
            remove_initial_volumes_panel,
            id="functional_settings",
            classes="components",
        )

        # Setting widgets for halfpipe settings
        workflowgroup_settings_panel = Container(
            SwitchWithInputBox(
                label="Number of nipype omp threads",
                value="1",
                classes="switch_with_input_box",
                id="nipype-omp-nthreads",
            ),
            Horizontal(
                Static("Path to the freesurfer license", id="the_static"), FileBrowser(path_to="Path"), id="fs-license-file"
            ),
            LabelledSwitch("Generate workflow suitable for running on a cluster", False),
            id="workflowgroup_settings",
            classes="components",
        )

        debuggroup_settings_panel = Container(
            LabelledSwitch("Debug", False),
            LabelledSwitch("Profile", False),
            LabelledSwitch("Watchdog", False),
            id="debuggroup_settings",
            classes="components",
        )
        rungroup_settings_panel = Container(
            SwitchWithInputBox(
                label="Merge subject workflows to n chunks",
                value="",
                switch_value=False,
                classes="switch_with_input_box",
                id="n-chunks",
            ),
            SwitchWithInputBox(
                label="Max chunk size",
                value="64",
                classes="switch_with_input_box",
                id="max-chunks",
            ),
            LabelledSwitch("Subject chunks", False),
            SwitchWithInputBox(
                label="Select which chunk to run",
                value="",
                switch_value=False,
                classes="switch_with_input_box",
                id="only-chunk-index",
            ),
            LabelledSwitch("Watchdog", False, id="nipype-resource-monitor"),
            SwitchWithInputBox(
                label="Nipype memory in GB",
                value="64",
                classes="switch_with_input_box",
                id="nipype-memory-gb",
            ),
            SwitchWithInputBox(
                label="Nipype number of processes",
                value="",
                switch_value=False,
                classes="switch_with_input_box",
                id="num-threads",
            ),
            SwitchWithInputBox(
                label="Nipype run plugin",
                value="MultiProc",
                classes="switch_with_input_box",
                id="nipype-run-plugin",
            ),
            LabelledSwitch("Nipype resource monitor", False),
            SwitchWithSelect(
                "Choose which intermediate files to keep",
                options=[("all", "all"), ("some", "some"), ("none", "none")],
                switch_value=True,
                id="keep",
            ),
            id="rungroup_settings",
            classes="components",
        )
        # The titles and the other styling settings need to be set in the compose because on load from a spec file
        # the settings from the spec file are passed as the default_settings variable and the whole widget needs to be
        # recomposed. When recomposing, the titles and etc. are deleted and can be newly added when they are defined
        # only in the compose function.
        functional_settings_panel.border_title = "Functional settings"
        anatomical_settings_panel.border_title = "Anatomical settings"
        slice_timing_panel.border_title = "Slice timing"
        slice_timing_panel.styles.height = "5"
        remove_initial_volumes_panel.border_title = "Initial volumes removal"
        slice_timming_info_panel.styles.visibility = "hidden"

        workflowgroup_settings_panel.border_title = "Workflow settings"
        debuggroup_settings_panel.border_title = "Debug settings"
        rungroup_settings_panel.border_title = "Run settings"

        yield anatomical_settings_panel
        yield functional_settings_panel
        yield workflowgroup_settings_panel
        yield debuggroup_settings_panel
        yield rungroup_settings_panel

    @on(Switch.Changed, "#via_algorithm_switch")
    def _on_via_algorithm_switch_changed(self, message):
        if message.value:
            self.get_widget_by_id("manualy_set_volumes_to_remove_label").update(
                "Turn of 'Detect non-steady-state via algorithm' to set manually number of initial volumes to remove"
            )
            self.get_widget_by_id("edit_button").styles.visibility = "hidden"
            self.get_widget_by_id("remove_volumes_value").styles.visibility = "hidden"
            ctx.spec.global_settings["dummy_scans"] = None
        else:
            self.get_widget_by_id("manualy_set_volumes_to_remove_label").update("Remove initial volumes from scans")
            self.get_widget_by_id("edit_button").styles.visibility = "visible"
            self.get_widget_by_id("remove_volumes_value").styles.visibility = "visible"
            # rais imidietely the modal
            self._on_edit_button_pressed()

    @on(Switch.Changed, "#run_reconall")
    def on_run_reconall_switch_changed(self, message: Message):
        ctx.spec.global_settings["run_reconall"] = message.value

    @work(exclusive=True, name="time_slicing_worker")
    @on(Switch.Changed, "#time_slicing_switch")
    async def on_time_slicing_switch_changed(self, message: Message):
        if message.value is True:
            self.get_widget_by_id("slice_timming_info").styles.visibility = "visible"
            self.get_widget_by_id("slice_timing").styles.height = "auto"

            ctx.spec.global_settings["slice_timing"] = True
            meta_step_instance = CheckBoldSliceEncodingDirectionStep(self.app, callback=self.callback_func)
            await meta_step_instance.run()
        else:
            ctx.spec.global_settings["slice_timing"] = False
            self.get_widget_by_id("slice_timming_info").styles.visibility = "hidden"
            self.get_widget_by_id("slice_timing").styles.height = "5"

            # need to delete in from all the bold filebojs
            for widget_id, the_dict in ctx.cache.items():
                # should always be there
                if "files" in the_dict:
                    if isinstance(the_dict["files"], File):
                        is_ok = True
                        if the_dict["files"].datatype != "func":
                            is_ok = False
                        if the_dict["files"].suffix != "bold":
                            is_ok = False
                        if is_ok:
                            # add dict if it does not exist
                            ctx.cache[widget_id]["files"].metadata.pop("slice_timing_code", None)
                            ctx.cache[widget_id]["files"].metadata.pop("slice_encoding_direction", None)

    def callback_func(self, message_dict: dict):
        """
        The callback function is passed to the FilePattern or CheckMetaData classes where they gather all of the messages
        so that the user can view them again.

        Parameters
        ----------
        message_dict : dict
            Dictionary containing key-value pairs where keys are strings
            and values are lists of strings. This dictionary is used to
            generate a formatted string with the key and concatenated
            values for each entry.
        """
        info_string = ""
        for key in message_dict:
            info_string += key + ": " + " ".join(message_dict[key]) + "\n"

        self.get_widget_by_id("slice_timming_info").update(info_string)

    def _add_slice_timing_from_file(self, path: str):
        # I think that this is a TODO
        select_widget = self.get_widget_by_id("select_slice_timing")
        if path is not None:
            self.time_slicing_options.insert(-1, path)
            select_widget.set_options([(str(value), value) for value in self.time_slicing_options])
            select_widget.value = path
            select_widget.styles.background = "50% green"
            pass
        else:
            select_widget.value = select_widget.BLANK
            select_widget.styles.background = "40% red"

    @on(Button.Pressed, "#edit_button")
    def _on_edit_button_pressed(self):
        def update_remove_initial_volumes_value(value: None | str):
            remove_volumes_value_widget = self.get_widget_by_id("remove_volumes_value")
            if value is not False:
                remove_volumes_value_widget.update(value)
                remove_volumes_value_widget.styles.border = ("solid", "green")
                ctx.spec.global_settings["dummy_scans"] = value

        self.app.push_screen(SetInitialVolumesRemovalModal(), update_remove_initial_volumes_value)
