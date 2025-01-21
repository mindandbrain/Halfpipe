# -*- coding: utf-8 -*-
# ok to review
from itertools import cycle

import pandas as pd
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Label, SelectionList
from textual.widgets.selection_list import Selection

from ..utils.confirm_screen import Confirm
from ..utils.draggable_modal_screen import DraggableModalScreen

cursors = cycle(["column", "row", "cell"])


class ContrastTableInputWindow(DraggableModalScreen):
    """
    ContrastTableInputWindow

    A modal window class for setting contrast values through a user interface.
    Inherits from `DraggableModalScreen` and provides functionality to capture and
    validate user inputs for contrast names and values.

    Attributes
    ----------
    CSS_PATH : list
        List containing paths to the CSS files for styling the window.

    Methods
    -------
    __init__(table_row_index, current_col_labels)
        Initializes the ContrastTableInputWindow instance with given row index and column labels.
    on_mount()
        Mounts the input widgets onto the window when the window is displayed.
    ok()
        Confirms the input values and performs validation checks.
    cancel_window()
        Cancels the window and dismisses it without saving user input.
    key_escape()
        Cancels the window and dismisses it when the escape key is pressed.
    _confirm_window()
        Validates the user inputs and updates the table row index if inputs are valid.
    _cancel_window()
        Dismisses the window without saving any user inputs.
    """

    CSS_PATH = ["tcss/contrast_table_input_window.tcss"]

    def __init__(self, table_row_index, current_col_labels) -> None:
        self.table_row_index = table_row_index
        self.current_col_labels = current_col_labels
        super().__init__()
        self.title_bar.title = "Set contrast values"

        input_elements = []
        for key, value in self.table_row_index.items():
            input_box = Input(
                placeholder="Value",
                value=value,
                name=key,
                classes="input_values",
            )
            label = Label(key)
            label.tooltip = value
            input_elements.append(Horizontal(label, input_box, classes="row_element"))
        self.widgets_to_mount = [
            Input(placeholder="Specify contrast name", id="contrast_name"),
            *input_elements,
            Horizontal(
                Button("Ok", classes="ok_button"),
                Button("Cancel", classes="cancel_button"),
                id="button_panel",
            ),
        ]

    def on_mount(self):
        self.content.mount(*self.widgets_to_mount)
        # self.get_widget_by_id("the_window").border_title = "Contrast"

    @on(Button.Pressed, "ContrastTableInputWindow .ok_button")
    def ok(self):
        self._confirm_window()

    @on(Button.Pressed, "ContrastTableInputWindow .cancel_button")
    def cancel_window(self):
        self._cancel_window()

    def key_escape(self):
        self._cancel_window()

    def _confirm_window(self):
        if self.get_widget_by_id("contrast_name").value in self.current_col_labels:
            self.app.push_screen(
                Confirm(
                    "The selected column name already exists",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Existing name",
                    classes="confirm_error",
                )
            )
        elif self.get_widget_by_id("contrast_name").value == "":
            self.app.push_screen(
                Confirm(
                    "Specify contrast name!",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Existing name",
                    classes="confirm_error",
                )
            )
        elif any(i.value == "" for i in self.query(".input_values")):
            self.app.push_screen(
                Confirm(
                    "Fill all values!",
                    left_button_text=False,
                    right_button_text="OK",
                    #  left_button_variant=None,
                    right_button_variant="default",
                    title="Existing name",
                    classes="confirm_error",
                )
            )
        else:
            for i in self.query(".input_values"):
                self.table_row_index[i.name] = i.value
            self.dismiss(self.get_widget_by_id("contrast_name").value)

    def _cancel_window(self):
        self.dismiss(False)


class ModelConditionsAndContrasts(Widget):
    """
    ModelConditionsAndContrasts class manages the condition values and contrast values for a given dataset, enabling users to
     add, remove, and update these values dynamically. It synchronizes selections between the condition list and the associated
     data table, ensuring consistency with any external modifications. The class uses pandas DataFrames to store and retrieve
     condition values, allowing seamless recovery and updating of data when required.

    Attributes
    ----------
    BORDER_TITLE : str
        Title of the border for the contrast values table.
    BINDINGS : list
        Key bindings for the add, remove, and submit actions.
    sort_type_cycle : cycle
        An iterator that cycles through sorting types: alphabetically, reverse_alphabetically, by_group, and reverse_by_group.
    condition_values : reactive[list]
        List of conditions in the selection, which can be modified externally and requires updates to the selection and table.

    Methods
    -------
    __init__(all_possible_conditions, feature_contrasts_dict=None, id=None, classes=None)
        Initializes the widget with available conditions, and an optional feature contrasts dictionary for pre-existing values.

    update_all_possible_conditions(all_possible_conditions)
        Updates the possible conditions in the data table and sets default conditions if a feature contrasts dictionary is
        provided.

    watch_condition_values()
        Watches the condition values and triggers an update when they change.

    compose()
        Composes the widget elements, including the selection list, data table, and control buttons.

    on_mount()
        Sets up the table and other widget components on mounting, including reading any defaults from the feature contrasts
        dictionary.

    update_table()
        Updates the data table based on changes in the selection list.

    set_heights()
        Adjusts the height of the widget and its components based on the number of rows in the selection list and data table.

    action_add_column()
        Adds a new column with contrast values to the data table.

    action_remove_column()
        Removes the currently selected column from the data table.

    action_submit()
        Submits the current contrast values, saving them for later use.

    add_col()
        Button event that triggers the action_add_column method.

    remove_col()
        Button event that triggers the action_remove_column method.

    sort_cols()
        Button event that triggers sorting of the table by row labels.

    key_c()
        Handles key press events for the data table.
    """

    BORDER_TITLE = "Model conditions & contrast vales"

    BINDINGS = [
        ("a", "add_column", "Add column"),
        ("r", "remove_column", "Add column"),
        ("s", "submit", "Submit"),
    ]

    sort_type_cycle = cycle(
        [
            "alphabetically",
            "reverse_alphabetically",
            "by_group",
            "reverse_by_group",
        ]
    )

    # condition_values: list of the conditions in the selection, this can be changed also externally by other widget
    # if so, the selection and the table need an update
    condition_values: reactive[list] = reactive([], init=False)

    def __init__(
        self,
        all_possible_conditions: list,
        feature_contrasts_dict: list,
        feature_conditions_list: list,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """The pandas dataframe is to remember all choices even when some images or conditions are turned off.
        This is because when they are turned on, the condition values will be also back.
        The feature_contrasts_dict is used when the widget is created either from read-in (from existing json file) or
        when duplicated.
        The tricky part in this widget is to keep sync between the selection list and the table and on top of  that
        with the images selection list from the upper widget. Also one needs to properly store and recover table values
        on change.
        The all_possible_conditions is a list of all conditions based on the available images (bold) files.
        The feature_contrasts_dict is reference to the list in the ctx.cache!
        """
        super().__init__(id=id, classes=classes)
        self.feature_contrasts_dict = feature_contrasts_dict
        self.feature_conditions_list = feature_conditions_list
        self.all_possible_conditions = all_possible_conditions
        self.row_dict: dict = {}
        self.update_all_possible_conditions(all_possible_conditions)

    def update_all_possible_conditions(self, all_possible_conditions: list) -> None:
        self.df = pd.DataFrame()
        self.df["condition"] = all_possible_conditions
        self.df.set_index("condition", inplace=True)
        # if there are dict entries then set defaults
        # if self.feature_contrasts_dict is not None:  # Ensure it is not None
        if self.feature_contrasts_dict != []:
            # convert dict to pandas
            for contrast_dict in self.feature_contrasts_dict:
                #   for row_index in self.df.index:
                for condition_name in contrast_dict["values"]:
                    self.df.loc[condition_name, contrast_dict["name"]] = contrast_dict["values"][condition_name]
            self.table_row_index = dict.fromkeys(list(self.feature_contrasts_dict[0]["values"].keys()))

    def watch_condition_values(self) -> None:
        self.update_condition_selection()

    def compose(self) -> ComposeResult:
        table = DataTable(zebra_stripes=True, header_height=2, id="contrast_table")
        # table = self.query_one(DataTable)
        # to init the table, stupid but nothing else worked
        table.add_column(label="temp", key="temp")
        # first case is used upon duplication or load, here we use the feature_conditions_list to add the rows to table
        if self.feature_conditions_list != []:
            # hence this list reflects already the selected images
            [table.add_row(None, label=o, key=o) for o in self.feature_conditions_list]
        # second case is standard case when a new task based feature is added, now we use all possible conditions
        else:
            [table.add_row(None, label=o, key=o) for o in self.all_possible_conditions]
        table.remove_column("temp")

        table.cursor_type = "column"
        table.zebra_stripes = True
        # read table defaults if there are some, this put columns into table (on load or on duplication)
        # if self.feature_contrasts_dict is not None:  # Ensure it is not None
        # the "or" is a must, one can make a duplicate from a widget where there are some conditions selections but there are
        # no columns in the table
        if self.feature_contrasts_dict != [] or self.feature_conditions_list != []:
            for contrast_dict in self.feature_contrasts_dict:
                table.add_column(contrast_dict["name"], key=contrast_dict["name"])
                for row_key in table.rows:
                    table.update_cell(row_key, contrast_dict["name"], contrast_dict["values"][row_key.value])
            condition_selection_list = [
                Selection(condition, condition, initial_state=(condition in self.feature_conditions_list), id=condition)
                for condition in self.all_possible_conditions
            ]
        else:
            condition_selection_list = [
                Selection(condition, condition, initial_state=True, id=condition) for condition in self.all_possible_conditions
            ]

        yield SelectionList[str](
            *condition_selection_list,
            id="model_conditions_selection",
        )
        yield HorizontalScroll(
            table,
            id="contrast_table_upper",
        )
        yield Horizontal(
            Button("Add contrast values", classes="add_button"),
            Button("Remove contrast values", classes="delete_button"),
            Button("Sort table", classes="sort_button"),
            id="button_panel",
        )

    def on_mount(self) -> None:
        self.set_heights()

    @on(SelectionList.SelectedChanged, "#model_conditions_selection")
    def update_table(self) -> None:
        """When the selection is changed, the table needs to be updated."""
        table = self.get_widget_by_id("contrast_table")

        row_dict = {}
        for r in table.rows:
            row_dict[r.value] = r

        # if there are more rows in the table than in selection, we need to find which one we need to remove
        if len(self.get_widget_by_id("model_conditions_selection").selected) < len(table.rows):
            out = list(set(row_dict.keys()) - set(self.get_widget_by_id("model_conditions_selection").selected))
            [table.remove_row(row_dict[o]) for o in out]
        # if there are less rows in the table than in selection, we need to find which one we need to add
        elif len(self.get_widget_by_id("model_conditions_selection").selected) > len(table.rows):
            out = list(set(self.get_widget_by_id("model_conditions_selection").selected) - set(row_dict.keys()))
            [table.add_row(*self.df.loc[o].values, label=o, key=o) for o in out]

        self.table_row_index = dict.fromkeys(sorted([r.value for r in table.rows]))
        self.sort_by_row_label(default="by_group")
        self.dump_contrast_values()

        self.set_heights()

    def set_heights(self):
        # if self.condition_values != [] or self.feature_contrasts_dict != []:
        # set the height based on the number of rows
        self.get_widget_by_id("contrast_table_upper").styles.height = (
            len(self.get_widget_by_id("model_conditions_selection").selected) + 6
        )
        self.get_widget_by_id("model_conditions_selection").styles.height = (
            len(self.get_widget_by_id("model_conditions_selection")._values) + 2
        )
        self.styles.height = (
            len(self.get_widget_by_id("model_conditions_selection").selected)
            + len(self.get_widget_by_id("model_conditions_selection")._values)
            + 14
        )
        # else:
        #     self.styles.height = 20

    def action_add_column(self):
        """Add column with new contrast values to te table."""

        def add_column(new_column_name: str):  # , new_column_values=None):
            # new_column_name is just the column label
            # is dictionary with the new column values
            table = self.get_widget_by_id("contrast_table")

            if new_column_name is not False:
                table.add_column(new_column_name, default=1, key=new_column_name)
                for row_key in table.rows:
                    table.update_cell(row_key, new_column_name, self.table_row_index[row_key.value])
                    self.df.loc[row_key.value, new_column_name] = self.table_row_index[row_key.value]
            else:
                pass
            self.dump_contrast_values()

        # start with opening of the modal screen
        self.app.push_screen(
            ContrastTableInputWindow(
                table_row_index=self.table_row_index,
                current_col_labels=self.df.columns.values,
            ),
            add_column,
        )

    async def action_remove_column(self):
        table = self.get_widget_by_id("contrast_table")
        if len(table.ordered_columns) != 0:
            row_key, column_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            table.remove_column(column_key)
            self.df = self.df.drop(column_key.value, axis=1)
            self.dump_contrast_values()

    async def action_submit(self):
        self.dump_contrast_values()

    @on(Button.Pressed, "ModelConditionsAndContrasts .add_button")
    async def add_col(self) -> None:
        await self.run_action("add_column()")

    @on(Button.Pressed, "ModelConditionsAndContrasts .delete_button")
    async def remove_col(self) -> None:
        await self.run_action("remove_column()")

    @on(Button.Pressed, "ModelConditionsAndContrasts .sort_button")
    async def sort_cols(self) -> None:
        self.sort_by_row_label()

    # def key_c(self):
    #     table = self.get_widget_by_id("contrast_table")
    #     table.cursor_type = next(cursors)

    def update_condition_selection(self):
        """When some images are selected/deselected, the condition selection needs to be upgraded
        and accordingly therefore the table.
        """
        conditions = self.condition_values

        condition_selection = self.get_widget_by_id("model_conditions_selection")
        available_conditions = list(condition_selection._option_ids.keys())

        if conditions != []:
            # this is to preserve the wanted order of the conditions
            if len(available_conditions) == 0:
                add_this_condtions = conditions
            else:
                add_this_condtions = list(set(conditions) - set(available_conditions))
                add_this_condtions.sort()

            for key in add_this_condtions:
                condition_selection.add_option(Selection(key, key, initial_state=True, id=key))
            for key in set(available_conditions) - set(conditions):
                condition_selection.remove_option(key)
        else:
            with condition_selection.prevent(SelectionList.SelectedChanged):
                condition_selection.clear_options()

        # now upgrade the table
        self.update_table()
        self.dump_contrast_values()

    def sort_by_row_label(self, default: str | None = None):
        """
        Parameters
        ----------
        default : str, optional
            Custom sort type to override the default cycling sort types.
        """
        condition_selection = self.get_widget_by_id("model_conditions_selection")
        groups = list(condition_selection._option_ids.keys())
        table = self.get_widget_by_id("contrast_table")
        # add this  column for sorting purpose, later it is removed
        table.add_column("condition", key="condition")
        for row_key in table.rows:
            table.update_cell(row_key, "condition", row_key.value)

        if default is None:
            sort_type = next(self.sort_type_cycle)
        else:
            sort_type = default
        if "alphabetically" in sort_type:

            def identity_func(value):
                return value

            sort_function = identity_func
        else:

            def find_group_index(element):
                return next(i for i, key in enumerate(groups) if element == key)

            sort_function = find_group_index

        if "reverse" in sort_type:
            reverse = True
        else:
            reverse = False

        table.sort(
            "condition",
            key=sort_function,
            reverse=reverse,
        )

        table.remove_column("condition")

    def dump_contrast_values(self) -> None:
        table = self.get_widget_by_id("contrast_table")
        df_filtered = self.df.loc[sorted([i.value for i in table.rows])]

        #  if self.feature_contrasts_dict is not None:  # Ensure it is not None
        self.feature_contrasts_dict.clear()
        # Iterate over each column in the DataFrame
        for column in df_filtered.columns:
            self.feature_contrasts_dict.append({"type": "t", "name": column, "values": df_filtered[column].to_dict()})

        self.feature_conditions_list.clear()
        self.feature_conditions_list.extend(df_filtered.index.values)
