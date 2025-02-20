# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from inflection import humanize, underscore

from ...model.model import FixedEffectsModelSchema, Model
from ...utils.format import format_like_bids
from ...utils.format import inflect_engine as p
from ..components import (
    MultipleChoiceInputView,
    SingleChoiceInputView,
    SpacerView,
    TextInputView,
    TextView,
)
from ..pattern import entity_display_aliases
from ..step import Step, YesNoStep
from ..utils import forbidden_chars
from .filter import MEModelMotionFilterStep
from .loop import AddAnotherModelStep
from .spreadsheet import SpreadsheetStep

bold_filedict = {"datatype": "func", "suffix": "bold"}
aggregate_order = ["dir", "run", "ses", "task"]


def _resolve_across(ctx, inputname):
    for obj in ctx.spec.features:
        if inputname == obj.name:
            return []
    for obj in ctx.spec.models:
        if inputname == obj.name:
            in_across_set = set(tuple(_resolve_across(ctx, input)) for input in obj.inputs)
            assert len(in_across_set) == 1, "Cannot resolve across"
            (in_across,) = in_across_set
            return [*in_across, obj.across]
    raise ValueError(f'Input "{inputname}" not found')


def _get_fe_aggregate(ctx, inputname, across):
    assert all(entity in aggregate_order for entity in across)

    # check if already exists
    for obj in ctx.spec.models:
        if obj.type != "fe":
            continue
        if hasattr(obj, "filters") and obj.filters is not None and len(obj.filters) > 0:
            continue
        if inputname not in obj.inputs or len(obj.inputs) > 1:
            continue
        if not hasattr(obj, "across"):
            continue

        obj_across = _resolve_across(ctx, obj.name)
        if tuple(obj_across) != tuple(across):
            continue

        return obj.name

    # need to create
    display_strs = [entity_display_aliases[entity] if entity in entity_display_aliases else entity for entity in across]
    acrossstr = " then ".join([p.plural(display_str) for display_str in display_strs])
    inputname_with_spaces = humanize(underscore(inputname))
    basename = format_like_bids(f"aggregate {inputname_with_spaces} across {acrossstr}")

    entity = across.pop()

    if len(across) > 0:
        inputname = _get_fe_aggregate(ctx, inputname, across)

    aggregatename = basename
    analysis_names = set(model_obj.name for model_obj in ctx.spec.models)
    i = 0
    while aggregatename in analysis_names:  # assure unique name
        aggregatename = f"{basename}{i}"
        i += 1

    modelobj = FixedEffectsModelSchema().load({"name": aggregatename, "inputs": [inputname], "type": "fe", "across": entity})
    assert isinstance(modelobj, Model)
    ctx.spec.models.insert(-1, modelobj)

    return modelobj.name


class ModelAggregateStep(Step):
    def setup(self, ctx):
        self.is_first_run = True
        self.choice = None

        # get entities to ask for

        model_obj = ctx.spec.models[-1]
        inputs = set(model_obj.inputs)
        assert inputs is not None and len(inputs) > 0

        featureobjs = []
        for obj in ctx.spec.features:
            if obj.name in inputs:
                if obj.type not in ["atlas_based_connectivity"]:
                    featureobjs.append(obj)

        filepaths = ctx.database.get(**bold_filedict)

        setting_filters = dict()
        for setting in ctx.spec.settings:
            setting_filters[setting["name"]] = setting.get("filters")

        self.feature_entities = dict()
        for obj in featureobjs:
            filters = setting_filters[obj.setting]
            feature_filepaths = [*filepaths]
            if filters is not None and len(filters) > 0:
                feature_filepaths = ctx.database.applyfilters(feature_filepaths, filters)
            # find all entities with more than one value for the given feature
            self.feature_entities[obj.name], _ = ctx.database.multitagvalset(aggregate_order, filepaths=feature_filepaths)

        entitiesset = set.union(*[set(entitylist) for entitylist in self.feature_entities.values()])

        across = ctx.spec.models[-1].across
        assert across not in entitiesset

        self.entities = [entity for entity in aggregate_order if entity in entitiesset]  # maintain order
        display_strs = [
            (entity_display_aliases[entity] if entity in entity_display_aliases else entity) for entity in self.entities
        ]
        self.options = [humanize(p.plural(display_str)) for display_str in display_strs]

        self.optionstr_by_entity = dict(zip(self.entities, self.options, strict=False))

        if len(self.options) > 0:
            self._append_view(TextView("Aggregate scan-level statistics before analysis?"))
            self.input_view = MultipleChoiceInputView(
                self.options,
                checked=[option for option in self.options if option != "task"],
            )
            self._append_view(self.input_view)
            self._append_view(SpacerView(1))

    def run(self, _):
        if not len(self.options) > 0:
            return self.is_first_run
        else:
            self.choice = self.input_view()
            if self.choice is None:
                return False
            return True

    def next(self, ctx):
        to_aggregate: dict[str, list[str]] = dict()
        if self.choice is not None:
            for entity in self.entities:
                optionstr = self.optionstr_by_entity[entity]
                if not self.choice[optionstr]:
                    continue
                for featurename, feature_entities in self.feature_entities.items():
                    if entity not in feature_entities:
                        continue
                    if featurename not in to_aggregate:
                        to_aggregate[featurename] = list()
                    to_aggregate[featurename].append(entity)

        for i, inputname in enumerate(ctx.spec.models[-1].inputs):
            if inputname in to_aggregate:
                # add to spec if not existing
                ctx.spec.models[-1].inputs[i] = _get_fe_aggregate(ctx, inputname, to_aggregate[inputname])

        if len(self.options) > 0 or self.is_first_run:
            self.is_first_run = False
            if ctx.spec.models[-1].type == "me":
                return MEModelMotionFilterStep(self.app)(ctx)
            elif ctx.spec.models[-1].type == "lme":
                return SpreadsheetStep(self.app)(ctx)
            else:
                raise ValueError(f'Unknown model type "{ctx.spec.models[-1].type}"')


class ModelFeaturesStep(Step):
    def setup(self, ctx):
        self.choice = None
        self.should_run = False
        self.is_first_run = True

        assert ctx.spec.features is not None

        self.namesset = set(feature.name for feature in ctx.spec.features if feature.type not in ["atlas_based_connectivity"])

        assert len(self.namesset) > 0

        if len(self.namesset) > 1:
            self.should_run = True

            self._append_view(TextView("Specify features to use"))

            names = sorted(list(self.namesset))

            self.input_view = MultipleChoiceInputView(names, checked=names, is_vertical=True)

            self._append_view(self.input_view)
            self._append_view(SpacerView(1))

    def run(self, _):
        if not self.should_run:
            return self.is_first_run
        else:
            self.choice = self.input_view()
            if self.choice is None:
                return False
            return True

    def next(self, ctx):
        if self.choice is not None:
            ctx.spec.models[-1].inputs = [feature for feature, is_selected in self.choice.items() if is_selected]
        elif len(self.namesset) == 1:
            ctx.spec.models[-1].inputs = [*self.namesset]

        if self.should_run or self.is_first_run:
            self.is_first_run = False

            return ModelAggregateStep(self.app)(ctx)


class ModelNameStep(Step):
    def setup(self, ctx):
        self._append_view(TextView("Specify model name"))

        assert ctx.spec.models is not None and len(ctx.spec.models) > 0

        self.names = set(model.name for model in ctx.spec.models)

        base = "model"
        suggestion = base
        index = 1
        while suggestion in self.names:
            suggestion = f"{base}{index}"
            index += 1

        self.input_view = TextInputView(text=suggestion, isokfun=lambda text: forbidden_chars.search(text) is None)

        self._append_view(self.input_view)
        self._append_view(SpacerView(1))

    def run(self, _):
        self.result = self.input_view()
        if self.result is None:  # was cancelled
            return False
        return True

    def next(self, ctx):
        assert self.result not in self.names, "Duplicate model name"

        ctx.spec.models[-1].name = self.result

        return ModelFeaturesStep(self.app)(ctx)


class ModelTypeStep(Step):
    is_vertical = True
    options = {"Intercept only": "me", "Linear model": "lme"}

    def setup(self, _):
        self._append_view(TextView("Specify model type"))
        self.input_view = SingleChoiceInputView(list(self.options.keys()), is_vertical=self.is_vertical)
        self._append_view(self.input_view)
        self._append_view(SpacerView(1))

    def run(self, _):
        self.choice = self.input_view()
        if self.choice is None:
            return False
        return True

    def next(self, ctx):
        if self.choice is None:
            return

        modelobj = Model(name=None, type=self.options[self.choice], across="sub")
        ctx.spec.models.append(modelobj)

        return ModelNameStep(self.app)(ctx)


class HasModelStep(YesNoStep):
    header_str = "Specify group-level model?"
    yes_step_type = ModelTypeStep
    no_step_type = None

    def _should_run(self, ctx):
        if hasattr(ctx.spec, "features") and ctx.spec.features is not None:
            for feature in ctx.spec.features:
                if hasattr(feature, "type") and feature.type != "atlas_based_connectivity":
                    return True

        self.choice = "No"
        return False


AddAnotherModelStep.yes_step_type = ModelTypeStep

ModelsStep = HasModelStep
