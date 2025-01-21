# -*- coding: utf-8 -*-
# ok (more-less) to review

import copy
import json
from collections import defaultdict
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widget import Widget
from textual.widgets import Button, Pretty

from ...model.feature import Feature
from ...model.file.bids import BidsFileSchema
from ...model.model import Model
from ...model.setting import SettingSchema
from ...model.spec import SpecSchema, save_spec
from ...utils.copy import deepcopy
from ..utils.confirm_screen import Confirm
from ..utils.context import ctx


class RunCLX(Widget):
    """
    RunCLX Class

    This class is responsible for managing the user interface that handles refreshing the data and updating the context
    based on user interactions.

    Attributes
    ----------
    old_cache : defaultdict or None
        A cache of old data, structured as a defaultdict of defaultdicts containing dictionaries.

    Methods
    -------
    __init__(**kwargs)
        Initializes the RunCLX class with only textual widget attributes.

    compose() -> ComposeResult
        Composes the UI by adding a ScrollableContainer with an output area and a refresh button.

    on_button_pressed()
        Handles the event when the refresh button is pressed. Dumps the current cache to the context
        and updates the output widget with the refreshed data.

    dump_dict_to_contex()
        Converts the cached data to the context format:
            1. Clears the existing data in the context.
            2. Iterates over the cache and fills the context with features, settings, and files.
            3. Handles specific cases for BIDS and non-BIDS files.
            4. Deep copies the current cache to old_cache.
            5. Refreshes available images in the context.
    """

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.old_cache: defaultdict[str, defaultdict[str, dict[str, Any]]] | None = None
        self.json_data = None

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Horizontal(
                Button("Refresh", id="refresh_button"), Button("Save", id="save_button"), Button("Run", id="run_button")
            )
            yield Pretty("", id="this_output")

    @on(Button.Pressed, "#run_button")
    def on_run_button_pressed(self):
        self.app.exit(result=ctx.workdir)

    @on(Button.Pressed, "#save_button")
    def on_save_button_pressed(self):
        def save(value):
            save_spec(ctx.spec, workdir=ctx.workdir)

        self.refresh_context()
        self.app.push_screen(
            Confirm(
                "The spec file was saved to working directory!",
                left_button_text=False,
                right_button_text="OK",
                right_button_variant="success",
                title="Spec file saved",
                classes="confirm_success",
            ),
            save,
        )

    @on(Button.Pressed, "#refresh_button")
    def on_refresh_button_pressed(self):
        self.refresh_context()

    def refresh_context(self):
        self.dump_dict_to_contex()
        self.json_data = SpecSchema().dumps(ctx.spec, many=False, indent=4, sort_keys=False)
        if self.json_data is not None:
            self.get_widget_by_id("this_output").update(json.loads(self.json_data))

    def dump_dict_to_contex(self, save=False):
        # the cache key logic goes like this: first it is the particular name of the main item, for example a feature called
        # 'foo' will produce a key "foo" this is the "name". Second, it is the main group type of the item, if it is the
        # feature then the group type is feature, if it is for example bold file pattern then it is the bold file pattern,
        # and third are the various own items of the group type, thus these vary from group to group
        # The reason why this goes name-group type-items is that it is easier to delete the particular main item if its name
        # is at the first level

        # clear the whole database and all other entries in the context object
        ctx.database.filepaths_by_tags = dict()
        ctx.database.tags_by_filepaths = dict()
        ctx.spec.features.clear()
        ctx.spec.settings.clear()
        ctx.spec.models.clear()
        ctx.spec.files.clear()
        print("ccccccccccccccccccccccccccccc cache", ctx.cache)
        # iterate now over the whole cache and fill the context object
        # the "name" is widget name carying the particular user choices, either a feature or file pattern
        for name in list(ctx.cache.keys()):  # Copy keys into a list to avoid changing dict size during iteration
            if ctx.cache[name]["features"] != {}:
                featureobj = Feature(name=name, type=ctx.cache[name]["features"]["type"])
                ctx.spec.features.append(featureobj)
                for key, value in ctx.cache[name]["features"].items():
                    # try:
                    print("keeeeeeeeeeeeeeeeeeeeeeeeeeeeeey features", key, value)
                    # for reho and falff smoothing is in features
                    if key == "smoothing" and value.get("fwhm") is None:
                        continue
                    setattr(ctx.spec.features[-1], key, value)

                    # except Exception:
                    #     exc_type, exc_value, exc_traceback = sys.exc_info()
                    #     print(f"An exception occurred: {exc_value}")
                    #     traceback.print_exception(exc_type, exc_value, exc_traceback)
            if ctx.cache[name]["settings"] != {}:
                ctx.spec.settings.append(SettingSchema().load({}, partial=True))
                for key, value in ctx.cache[name]["settings"].items():
                    # try:
                    # Skip keys based on specific conditions
                    print("keeeeeeeeeeeeeeeeeeeeeeeeeeeeeey", key, value)
                    if (
                        (key == "bandpass_filter" and value.get("type") is None)
                        or (key == "smoothing" and value.get("fwhm") is None)
                        or (key == "grand_mean_scaling" and value.get("mean") is None)
                    ):
                        continue

                    # Special handling for "filters", if there are no filters, than put there just empty list
                    if key == "filters":
                        filters = value
                        task_images = ctx.get_available_images["task"]

                        # Check if filters is empty, matches task images, or contains an empty 'values' list in
                        # any dictionary
                        if (
                            not filters  # Filters is empty
                            or set(filters[0].get("values", [])) == set(task_images)  # Matches task images
                            or any(
                                isinstance(item, dict) and not item.get("values")  # Dict with empty "values"
                                for item in filters
                            )
                        ):
                            value = []  # Overwrite filters value with an empty list

                    # Apply the value to the settings object
                    setattr(ctx.spec.settings[-1], key, value)
                # except Exception as e:
                #     print(f"An exception occurred: {e}")
                #     traceback.print_exc()

                # this is for the case of falff
                if "unfiltered_setting" in ctx.cache[name]:
                    unfiltered_setting = deepcopy(ctx.spec.settings[-1])
                    unfiltered_setting["name"] = ctx.cache[name]["unfiltered_setting"]["name"]
                    unfiltered_setting["bandpass_filter"] = None  # remove bandpass filter, keep everything else
                    ctx.spec.settings.append(unfiltered_setting)
            if ctx.cache[name]["models"] != {}:
                modelobj = Model(name=ctx.cache[name]["models"]["name"], type=ctx.cache[name]["type"], across="sub")
                ctx.spec.models.append(modelobj)
                for key, value in ctx.cache[name]["models"].items():
                    setattr(ctx.spec.models[-1], key, value)

            if ctx.cache["bids"]["files"] != {} and name == "bids":
                ctx.put(BidsFileSchema().load({"datatype": "bids", "path": ctx.cache["bids"]["files"]}))

            if ctx.cache[name]["files"] != {} and name != "bids":
                ctx.spec.files.append(ctx.cache[name]["files"])
                ctx.database.put(ctx.spec.files[-1])  # we've got all tags, so we can add the fileobj to the index
        self.old_cache = copy.deepcopy(ctx.cache)
        # refresh at the end available images
        ctx.refresh_available_images()
