# -*- coding: utf-8 -*-


from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Select, SelectionList, Static, Switch
from textual.widgets.selection_list import Selection

from ...ingest.spreadsheet import read_spreadsheet
from ..utils.context import ctx
from ..utils.custom_switch import TextSwitch
from ..utils.draggable_modal_screen import DraggableModalScreen
from ..utils.file_browser_modal import FileBrowserModal, path_test_with_isfile_true
from ..utils.multichoice_radioset import MultipleRadioSet


class ModelTemplate(Widget):
    """
    FeatureTemplate

    A widget for creating and managing feature-based settings and selections within a user interface. This widget
    handles both the initialization of a new widget and the loading of settings from a specification file, adapting
    its behavior accordingly.

    Attributes
    ----------
    entity : str
        An identifier for the type of entity the widget interacts with.
    filters : dict
        A dictionary specifying the datatype and suffix to filter the database queries.
    featurefield : str
        The specific feature field in the settings.
    type : str
        The type of the feature.
    file_panel_class : type
        The class used for the file panel within this widget.
    feature_dict : dict
        A dictionary containing feature-specific settings and values.
    setting_dict : dict
        A dictionary containing general settings and configuration values.
    event_file_pattern_counter : int
        A counter for file patterns.
    tagvals : list
        A list of available tags for selection.
    bandpass_filter_low_key : str
        The key for the low-pass filter setting.
    bandpass_filter_high_key : str
        The key for the high-pass filter setting.
    images_to_use : dict
        A dictionary specifying which images to use, keyed by task.
    confounds_options : dict
        Available options for confounds removal, with their descriptions and default states.
    preprocessing_panel : Vertical
        A panel containing pre-processing options such as smoothing, mean scaling, and temporal filtering.
    images_to_use_selection_panel : SelectionList
        A panel containing the selection list of images to use.
    tag_panel : SelectionList
        A panel containing the selection list of tags.

    Methods
    -------
    __init__(this_user_selection_dict, id=None, classes=None)
        Initializes the widget with user selections and settings.
    compose()
        Composes the user interface elements within the widget.
    on_file_panel_file_item_is_deleted(message)
        Handles the event when a file item is deleted from the file panel.
    on_file_panel_changed(message)
        Handles the event when the file panel changes, updating the tag selection.
    """

    # filters: dict = {"datatype": "", "suffix": ""}
    type: str = ""
    bold_filedict = {"datatype": "func", "suffix": "bold"}
    aggregate_order = ["dir", "run", "ses", "task"]

    # Check if any dictionary in the list has the required key-value pairs
    def extract_from_existing_filters(self, filter_type_identifier):
        for filter_dict in self.model_dict["filters"]:
            if filter_type_identifier.items() <= filter_dict.items():
                return filter_dict
        return None

    def __init__(self, this_user_selection_dict: dict, id: str | None = None, classes: str | None = None) -> None:
        """At the beginning there is a bunch of 'if not in'. If a new widget is created the pass
        this_user_selection_dict is empty and the nested keys need some initialization. On the other
        hand, if a new widget is created automatically on spec file load then this dictionary is not empty and these
        values are then used for the various widgets within this widget.
        """
        super().__init__(id=id, classes=classes)
        self.model_dict = this_user_selection_dict["models"]
        self.model_dict.setdefault("type", self.type)
        self.model_dict.setdefault("filters", [])

        # In case of loading from a file or duplicating, we check whether there are some cutoffs made, if not then we switch
        # off the cutoff widget switch. It is enough to just check one of the cutoffs in the filter field.
        if (
            self.model_dict["filters"] != []
            and self.extract_from_existing_filters({"type": "cutoff", "field": "fd_mean"}) is not None
        ):
            cutoff_default_value = False
        else:
            cutoff_default_value = True

        # We need to field the filter dictionaries either from existing fields or assign default values to them.
        self.fd_mean_cutoff_dict = self.extract_from_existing_filters({"type": "cutoff", "field": "fd_mean"}) or {
            "type": "cutoff",
            "action": "exclude",
            "field": "fd_mean",
            "cutoff": "0.5",
        }

        self.fd_perc_cutoff_dict = self.extract_from_existing_filters({"type": "cutoff", "field": "fd_perc"}) or {
            "type": "cutoff",
            "action": "exclude",
            "field": "fd_perc",
            "cutoff": "10.0",
        }

        if self.model_dict["filters"] == []:
            self.model_dict["filters"].append(self.fd_mean_cutoff_dict)
            self.model_dict["filters"].append(self.fd_perc_cutoff_dict)

        # self.model_dict.setdefault("inputs", [])
        # First find all available tasks, assign True to all of them
        self.tasks_to_use: dict | None = {}
        for w in ctx.cache:
            if "features" in ctx.cache[w] and ctx.cache[w]["features"] != {}:
                if ctx.cache[w]["features"]["type"] == "task_based":
                    self.tasks_to_use[ctx.cache[w]["features"]["name"]] = True

        # If there are no pre-existing cutoff filters, then we just assign the keys from tasks_to_use dict, otherwise
        # we change values of the keys in tasks_to_use to dict to False if there are not present in the 'inputs' dict.
        if "inputs" not in self.model_dict:
            # self.model_dict["inputs"] = [task for task in self.tasks_to_use.keys() if self.tasks_to_use[task] is True]
            self.model_dict["inputs"] = self.tasks_to_use.keys()
        else:
            self.tasks_to_use = {task_key: task_key in self.model_dict["inputs"] for task_key in self.tasks_to_use.keys()}

        self.tasks_to_use_selection_panel = SelectionList[str](
            *[Selection(task, task, self.tasks_to_use[task]) for task in self.tasks_to_use.keys()],
            id="tasks_to_use_selection",
            classes="components",
        )

        self.cutoff_panel = Vertical(
            Grid(
                Static("Exclude subjects based on movements", classes="description_labels"),
                TextSwitch(value=cutoff_default_value, id="exclude_subjects"),
            ),
            Grid(
                Static("Specify the maximum allowed mean framewise displacement in mm", classes="description_labels"),
                Input(value=str(self.fd_mean_cutoff_dict["cutoff"]), placeholder="value", id="cutoff_fd_mean"),
                id="cutoff_fd_mean_panel",
            ),
            Grid(
                Static(
                    "Specify the maximum allowed percentage of frames above the framewise displacement threshold of 0.5 mm",
                    classes="description_labels",
                ),
                Input(value=str(self.fd_perc_cutoff_dict["cutoff"]), placeholder="value", id="cutoff_fd_perc"),
                id="cutoff_fd_perc_panel",
            ),
            id="cutoff_panel",
            classes="components",
        )

    async def on_mount(self) -> None:
        if self.tasks_to_use is not None:
            self.get_widget_by_id("tasks_to_use_selection").border_title = "Tasks to use"
        self.get_widget_by_id("cutoff_panel").border_title = "Cutoffs"

    @on(Input.Changed, "#cutoff_fd_mean")
    def _on_cutoff_fd_mean_input_changed(self, message: Message):
        self.fd_mean_cutoff_dict["cutoff"] = message.value

    @on(Input.Changed, "#cutoff_fd_perc")
    def _on_cutoff_fd_perc_input_changed(self, message: Message):
        self.fd_perc_cutoff_dict["cutoff"] = message.value

    @on(SelectionList.SelectedChanged, "#tasks_to_use_selection")
    def _on_selection_list_changed(self):
        self.model_dict["inputs"] = self.get_widget_by_id("tasks_to_use_selection").selected

    @on(Switch.Changed, "#exclude_subjects")
    def on_exclude_subjects_switch_changed(self, message: Message):
        if message.value is True:
            self.model_dict["filters"].append(self.fd_mean_cutoff_dict)
            self.model_dict["filters"].append(self.fd_perc_cutoff_dict)
            self.get_widget_by_id("cutoff_fd_mean_panel").styles.visibility = "visible"
            self.get_widget_by_id("cutoff_fd_perc_panel").styles.visibility = "visible"
            self.get_widget_by_id("cutoff_fd_perc_panel").styles.height = "auto"
        else:
            self.model_dict["filters"].remove(self.fd_mean_cutoff_dict)
            self.model_dict["filters"].remove(self.fd_perc_cutoff_dict)
            self.get_widget_by_id("cutoff_fd_mean_panel").styles.visibility = "hidden"
            self.get_widget_by_id("cutoff_fd_perc_panel").styles.visibility = "hidden"
            self.get_widget_by_id("cutoff_fd_perc_panel").styles.height = 7


class InterceptOnlyModel(ModelTemplate):
    type = "me"

    def __init__(self, this_user_selection_dict=None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(this_user_selection_dict=this_user_selection_dict, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="top_container_models"):
            if self.tasks_to_use is not None:
                yield self.tasks_to_use_selection_panel
            yield self.cutoff_panel


class LinearModel(ModelTemplate):
    type = "lme"

    def __init__(self, this_user_selection_dict=None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(this_user_selection_dict=this_user_selection_dict, id=id, classes=classes)
        self.spreadsheet_filepaths = {}
        for key in ctx.cache:
            print("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk", key)
            if key.startswith("__spreadsheet_file_"):
                print("eeeeeeeeeeee", key)
                self.spreadsheet_filepaths[key] = ctx.cache[key]["files"]["path"]
        print("self.spreadsheet_filepathsself.spreadsheet_filepathsself.spreadsheet_filepaths", self.spreadsheet_filepaths)
        # self.options: dict = {f: (f, True if f == filepaths[-1] else False) for f in filepaths} if filepaths else {}

        # there has to be button to Add new spreadsheet
        self.spreadsheet_panel = Vertical(
            # Static('No spreadsheet selected!', id='spreadsheet_path_label'),
            Select([(i[1], i[0]) for i in self.spreadsheet_filepaths.items()], id="spreadsheet_selection"),
            Horizontal(
                Button("Add", id="add_spreadsheet"),
                Button("Delete", id="delete_spreadsheet"),
                Button("Details", id="details_spreadsheet"),
            ),
            id="spreadsheet_selection_panel",
            classes="components",
        )
        self.spreadsheet_panel.border_title = "Covariates/group data spreadsheet file"

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="top_container_models"):
            if self.tasks_to_use is not None:
                yield self.tasks_to_use_selection_panel
            yield self.cutoff_panel
            yield self.spreadsheet_panel

    @on(Button.Pressed, "#add_spreadsheet")
    async def _on_button_select_spreadsheet_pressed(self):
        def update_spreadsheet_label(new_spreadsheet_selection):
            print("ffffffffffffffffff", new_spreadsheet_selection)
            if new_spreadsheet_selection is not False:
                self.spreadsheet_filepaths[new_spreadsheet_selection[0]] = new_spreadsheet_selection[1]
                self.get_widget_by_id("spreadsheet_selection").set_options(
                    [(i[1], i[0]) for i in self.spreadsheet_filepaths.items()]
                )
                self.get_widget_by_id("spreadsheet_selection").value = new_spreadsheet_selection[0]
                # self.get_widget_by_id('spreadsheet_path_label').update(selected_path)
                # self.get_widget_by_id("spreadsheet_path_label").styles.border = ("solid", "green")
                self.spreadsheet_df = read_spreadsheet(new_spreadsheet_selection[1])

        await self.app.push_screen(AddSpreadsheetModal(), update_spreadsheet_label)

    @on(Select.Changed, "#spreadsheet_selection")
    async def _on_spreadsheet_selection_changed(self):
        metadata = ctx.cache[self.get_widget_by_id("spreadsheet_selection").value]["files"]["metadata"]
        print("iiiiiiiiiiiiiiiiiiiiiiiis<<<<<<?????????", metadata)

        sub_panels = []
        self.variables = []
        for metadata_item in metadata:
            variable_name = metadata_item["name"]
            if metadata_item["type"] != "id":
                self.variables.append(variable_name)
            if metadata_item["type"] == "categorical":
                print("eeeeeeeeeeeeeeeeeeee", metadata_item["levels"])
                sub_panels.append(
                    Vertical(
                        Static(variable_name, classes="level_labels"),
                        SelectionList[str](
                            *[Selection(str(v), str(v), True) for v in metadata_item["levels"]],
                            classes="level_selection",
                            id=variable_name + "_panel",
                        ),
                        classes="level_sub_panels",
                    )
                )
                self.model_dict["filters"].append(
                    {
                        "type": "group",
                        "action": "include",
                        "variable": variable_name,
                        "levels": list(set(self.spreadsheet_df.loc[:, variable_name])),
                    }
                )

        await self.mount(
            Container(
                Static(
                    "Select the subjects to include in this analysis by their categorical variables\n\
For multiple categorical variables, the intersecion of the groups will be used.",
                    id="levels_instructions",
                ),
                Horizontal(
                    *sub_panels,
                    id="levels_panel",
                ),
                id="top_levels_panel",
                classes="components",
            ),
            after=self.get_widget_by_id("spreadsheet_selection_panel"),
        )
        await self.mount(
            Container(
                Static("Specify the variables to add to the model", id="model_variables_instructions"),
                SelectionList[str](
                    *[Selection(str(v), str(v), True) for v in self.variables], classes="model_variables_selection"
                ),
                id="top_model_variables_panel",
                classes="components",
            ),
            after=self.get_widget_by_id("top_levels_panel"),
        )
        self.get_widget_by_id("top_levels_panel").border_title = "Subjects to include by their categorical variables"
        self.get_widget_by_id("top_model_variables_panel").border_title = "Model variables"

    @on(SelectionList.SelectedChanged, ".level_selection")
    def _on_level_sub_panels_selection_list_changed(self, message):
        print("qqqqqqqqqqq", message.control.id)
        print("qqqqqqqqqqq", message.control.selected)
        variable_name = message.control.id[:-6]
        filter_type_identifier = {
            "type": "group",
            "action": "include",
            "variable": variable_name,
        }
        filter_dict = self.extract_from_existing_filters(filter_type_identifier)
        filter_dict["levels"] = message.control.selected
        print("cccccccccccccccc", ctx.cache)


class AddSpreadsheetModal(DraggableModalScreen):
    """
    SelectionModal(options=None, title="", instructions="Select", id=None, classes=None)

    Parameters
    ----------
    options : dict, optional
        A dictionary containing the options for the radio buttons,
        where keys are the option identifiers and values are the
        display text for each option. If not provided, defaults to
        {"a": "A", "b": "B"}.
    title : str, optional
        The title of the modal window, by default an empty string.
    instructions : str, optional
        Instructions or description to be displayed at the top of
        the modal window, by default "Select".
    id : str, optional
        An optional identifier for the modal window, by default None.
    classes : str, optional
        An optional string of classes for applying styles to the
        modal window, by default None.

    Attributes
    ----------
    title_bar.title : str
        Sets the title of the modal window.
    instructions : str
        Holds the instruction text for the modal window.
    widgets_to_mount : list
        A list of widgets to be mounted on the modal window, including
        title, radio buttons, and OK/Cancel buttons.
    choice : str or list
        The selected choice from the radio buttons, defaults to a
        placeholder "default_choice???todo".

    Methods
    -------
    on_mount()
        Called when the window is mounted. Mounts the content widgets.
    _on_ok_button_pressed()
        Handles the OK button press event, dismissing the modal window
        with the current choice.
    _on_cancel_button_pressed()
        Handles the Cancel button press event, dismissing the modal
        window with None value.
    _on_radio_set_changed(event)
        Handles the event when the radio button selection changes.
        Updates the choice attribute with the selected option key.
    """

    instance_count = 0

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.title_bar.title = "Path to the spreadsheet"
        self.instructions = "Select or add path of the covariates/group data spreadsheet file"
        filepaths = ctx.database.get(datatype="spreadsheet")
        # filepaths = ctx.get_spreadsheet_paths
        self.cache_name = "__spreadsheet_file_" + str(self.instance_count)
        self.instance_count += 1

        print("fffffffffffffffffff", filepaths)
        # self.options: dict = {f: (f, True if f == filepaths[-1] else False) for f in filepaths} if filepaths else {}
        self.last_selected = list(filepaths)[-1] if filepaths != set() else None

        # In some cases the user just must made some choice in the selection. In particular this is the case when one is
        # some of the Meta classes (CheckMeta...) are in action. Returning from this stage by hitting the cancel button would
        # not make sense.
        button_panel = Horizontal(
            Button("OK", id="ok"), Button("Cancel", id="cancel"), id="button_panel", classes="components"
        )

        self.widgets_to_mount = [
            ScrollableContainer(
                Container(
                    Static(self.instructions, id="title"),
                    Horizontal(
                        Button("Browse", id="browse"),
                        Static("No spreadsheet selected!", id="spreadsheet_path_label"),
                    ),
                    id="spreadsheet_path_panel",
                    classes="components",
                ),
                button_panel,
                id="top_container",
            )
        ]

        # self.choice: str | list = self.options.keys()[0]

    async def on_mount(self) -> None:
        """Called when the window is mounted."""
        await self.content.mount(*self.widgets_to_mount)
        self.get_widget_by_id("spreadsheet_path_panel").border_title = "Spreadsheet path"

    async def update_spreadsheet_list(self, spreadsheet_path: str | bool):
        if spreadsheet_path != "" and spreadsheet_path is not False:
            self.get_widget_by_id("spreadsheet_path_label").update(spreadsheet_path)
            # df = read_spreadsheet(spreadsheet_path)
            self.spreadsheet_df = read_spreadsheet(spreadsheet_path)
            # print("dddddddddddddddddd", df)
            # print("ccccccccccccc", list(df.columns.values))
            # file_name = Path(spreadsheet_path).stem
            print("file_name")

            ctx.cache[self.cache_name]["files"] = {"datatype": "spreadsheet", "path": spreadsheet_path, "metadata": []}
            for i, col_label in enumerate(self.spreadsheet_df.columns):
                type = "id" if i == 0 else "continuous"
                ctx.cache[self.cache_name]["files"]["metadata"].append({"name": col_label, "type": type})

            print("ccccccccccccccccccccc", ctx.cache)

            await self.mount(
                Container(
                    Static("Specify the column data types", id="column_assignement_label"),
                    MultipleRadioSet(
                        horizontal_label_set=["id", "continuous", "categorical"],
                        vertical_label_set=list(self.spreadsheet_df.columns.values),
                        default_value_column=1,
                        unique_first_column=True,
                        id="column_assignement",
                    ),
                    id="column_assignement_top_container",
                    classes="components",
                ),
                after=self.get_widget_by_id("spreadsheet_path_panel"),
            )
            self.get_widget_by_id("column_assignement_top_container").border_title = "Column data types"

            # await self.mount(
            #     Horizontal(
            #         Static('Select the subjects to include in this analysis by their categorical')
            #         id='levels_panel',
            #         classes='components'
            #     ),
            #     after=self.get_widget_by_id("column_assignement"),
            # )

            # If there are no options yet, then skip deselect.

            # if self.last_selected is not None:
            #     self.get_widget_by_id('selection_set').deselect(self.last_selected)
            #
            # self.get_widget_by_id('selection_set').add_option((spreadsheet_path, spreadsheet_path, True))
            # ctx.spec.files.append(SpreadsheetFileSchema().load({"datatype": "spreadsheet", "path": spreadsheet_path}))
            # # ctx.spreadsheet_paths.append(spreadsheet_path)
            # self.last_selected = spreadsheet_path

    @on(MultipleRadioSet.Changed)
    def on_radio_set_changed(self, message):
        # Extract the row number and column label
        row_number = int(message.row.replace("row_radio_sets_", ""))
        col_label = self.spreadsheet_df.columns[row_number]

        # Get unique levels from the selected column
        levels = list(self.spreadsheet_df.iloc[:, row_number].unique())

        # Filter out existing metadata for the column
        metadata = ctx.cache[self.cache_name]["files"]["metadata"]
        metadata = [item for item in metadata if item.get("name") != col_label]

        # Determine the metadata type based on the column
        metadata_entry = {"name": col_label}
        if message.column == 1:
            metadata_entry["type"] = "id"
        elif message.column == 2:
            metadata_entry["type"] = "categorical"
            metadata_entry["levels"] = levels
        elif message.column == 3:
            metadata_entry["type"] = "continuous"

        # Append the updated metadata entry
        metadata.append(metadata_entry)
        ctx.cache[self.cache_name]["files"]["metadata"] = metadata

    #     row_number = int(message.row.replace('row_radio_sets_', ''))
    #     label = self.spreadsheet_df.columns[row_number]
    #     levels = list(set(self.spreadsheet_df.iloc[:, row_number]))
    #     ctx.cache[self.cache_name]['files']['metadata'] = [item for item in self.cache_name]['files']['metadata'] if
    #     item.get(
    #         "name") != col_label]
    #
    #     if message.column == 1:
    #         ctx.cache[self.cache_name]['files']['metadata'].append({"name": col_label, "type": 'id')
    #     if message.column == 2:
    #         ctx.cache[self.cache_name]['files']['metadata'].append({"name": col_label, "type": 'categorical', 'levels':l
    #         evels)
    #     elif message.column == 3:
    #         ctx.cache[self.cache_name]['files']['metadata'].append({"name": col_label, "type": 'continous')

    #     print('iiiiiiiiiiiiiii', message.control.id)
    #     print('mnmmmmmmmmmmmmmmmmmmm', message.column)
    #     print('vvvvvvvvvvvvvvvvvvvvvvvv', message.row)
    #     row_number = int(message.row.replace('row_radio_sets_', ''))
    #     label = self.spreadsheet_df.columns[row_number]
    #
    #     if message.column == 2:
    #         print('ccccccccccccccccccccccccccccategorical!!!!!!!1')
    #         # this is df column number, in the widget the column names are the rows of the table
    #         print('self.spreadsheet_df.columns[]', self.spreadsheet_df.columns[row_number])
    #         print('eeeeeeeeeee', list(set(self.spreadsheet_df.iloc[:,row_number])))
    #         # self.spreadsheet_df.columns[]
    #         self.get_widget_by_id('levels_panel').mount(
    #             # SelectionList[int](
    #             #     ("Falken's Maze", 0, True),
    #             #     ("Black Jack", 1),
    #             #     ("Gin Rummy", 2),
    #             # ),
    #             Vertical(
    #                 Static(label, classes='level_labels'),
    #                 SelectionList[str](
    #                     *[Selection(str(v), str(v), True) for v in list(set(self.spreadsheet_df.iloc[:,row_number]))],
    #                     classes='level_selection'),
    #                 id=label+'_panel',
    #                 classes='level_sub_panels'
    #             )
    #             # after=self.get_widget_by_id("column_assignement"),
    #         )
    #     elif message.column != 2:
    #         print('ssssss')
    #         # print('qqqqqqqqqqqqqqq', self.query_one('#'+label+'_panel'))
    #         self.get_widget_by_id(label+'_panel').remove()
    #
    #         # self.remove(self.get_widget_by_id(self.query('#'+label+'_panel')))
    #         # Now me must check whether we must unmount a widget and if yes, then unmount it

    @on(Button.Pressed, "#browse")
    async def _on_add_button_pressed(self):
        await self.app.push_screen(
            FileBrowserModal(title="Select spreadsheet", path_test_function=path_test_with_isfile_true),
            self.update_spreadsheet_list,
        )

    @on(Button.Pressed, "#ok")
    def _on_ok_button_pressed(self):
        # create new file item
        # dismiss some identification of it
        print("cccccccccccccccc", ctx.cache)
        self.dismiss((self.cache_name, ctx.cache[self.cache_name]["files"]["path"]))

        # selected = self.get_widget_by_id("selection_set").selected
        # if selected != []:
        #     self.dismiss(selected[0])
        # else:
        #     self.dismiss(False)

    @on(Button.Pressed, "#cancel")
    def _on_cancel_button_pressed(self):
        self.dismiss(False)

    def request_close(self):
        self.dismiss(False)

    #
    # @on(SelectionList.SelectionToggled, "#selection_set")
    # def _on_selection_set_toggled(self, message):
    #     selected_value = message.selection
    #     message.control.deselect(self.last_selected)
    #     self.last_selected = selected_value
