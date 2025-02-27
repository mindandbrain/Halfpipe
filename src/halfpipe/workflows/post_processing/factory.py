# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from abc import abstractmethod
from dataclasses import dataclass
from math import isclose
from typing import Callable, Generic, Hashable, TypeVar

from nipype.pipeline import engine as pe

from ...collect.metadata import collect_metadata
from ...logging import logger
from ...utils.copy import deepcopyfactory
from ...utils.hash import b32_digest
from ..bypass import init_bypass_wf
from ..factory import Factory, FactoryContext
from ..fmriprep import FmriprepFactory
from ..memory import MemoryCalculator
from ..resampling.factory import AltBOLDFactory
from .bandpass_filter import BandpassFilterTuple, init_bandpass_filter_wf
from .confounds import init_confounds_regression_wf, init_confounds_select_wf
from .fmriprep_adapter import init_fmriprep_adapter_wf
from .grand_mean_scaling import init_grand_mean_scaling_wf
from .ica_aroma import init_ica_aroma_components_wf, init_ica_aroma_regression_wf
from .output import init_setting_output_wf
from .setting_adapter import init_setting_adapter_wf
from .smoothing import init_smoothing_wf

alphabet = "abcdefghijklmnopqrstuvwxzy"

T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class SettingTuple(Generic[T]):
    value: T
    suffix: str | None


@dataclass(frozen=True)
class LookupTuple(Generic[T]):
    setting_tuple: SettingTuple[T]
    memcalc: MemoryCalculator


class ICAAROMAComponentsFactory(Factory):
    def __init__(self, ctx, fmriprep_factory: Factory, alt_bold_factory: AltBOLDFactory):
        super(ICAAROMAComponentsFactory, self).__init__(ctx)

        self.alt_bold_factory = alt_bold_factory
        self.fmriprep_factory = fmriprep_factory

    def setup(self):
        prototype = init_ica_aroma_components_wf(workdir=str(self.ctx.workdir))
        self.wf_name = prototype.name

    def get(self, source_file, **_):
        hierarchy = self._get_hierarchy("post_processing_wf", source_file=source_file)
        wf = hierarchy[-1]

        vwf = wf.get_node(self.wf_name)
        connect = False

        if vwf is None:
            connect = True

            memcalc = MemoryCalculator.from_bold_file(source_file)
            vwf = init_ica_aroma_components_wf(workdir=str(self.ctx.workdir), memcalc=memcalc)

            for node in vwf._get_all_nodes():
                memcalc.patch_mem_gb(node)

            wf.add_nodes([vwf])

        assert isinstance(vwf, pe.Workflow)
        inputnode = vwf.get_node("inputnode")
        assert isinstance(inputnode, pe.Node)
        hierarchy.append(vwf)

        if connect:
            inputnode.inputs.tags = self.ctx.database.tags(source_file)
            self.ctx.database.fillmetadata("repetition_time", [source_file])
            inputnode.inputs.repetition_time = self.ctx.database.metadata(source_file, "repetition_time")
            self.alt_bold_factory.connect(hierarchy, inputnode, source_file=source_file)
            self.fmriprep_factory.connect(hierarchy, inputnode, source_file=source_file)

        outputnode = vwf.get_node("outputnode")

        return hierarchy, outputnode


class LookupFactory(Factory):
    def __init__(self, ctx, previous_factory: Factory):
        super(LookupFactory, self).__init__(ctx)

        self.wf_names: dict[SettingTuple, str] = dict()
        self.wf_factories: dict[LookupTuple, Callable] = dict()

        self.tpl_by_setting_name: dict[str, SettingTuple] = dict()

        self.previous_factory = previous_factory

    def setup(self) -> None:
        setting_names = [setting["name"] for setting in self.ctx.spec.settings]

        previous_tpls: list[SettingTuple] = []

        newsuffix_by_prevtpl: dict[SettingTuple, str] | None = None

        if isinstance(self.previous_factory, LookupFactory):
            if len(self.previous_factory.tpl_by_setting_name) > 0:
                previous_tpls.extend(set(self.previous_factory.tpl_by_setting_name.values()))

                # 2**16 values for suffix should be sufficient to avoid collisions
                newsuffixes = [b32_digest(tpl)[:4] for tpl in previous_tpls]

                newsuffix_by_prevtpl = dict(zip(previous_tpls, newsuffixes, strict=False))

        suffixes = []
        for name in setting_names:
            suffix = None
            if isinstance(self.previous_factory, LookupFactory):
                if isinstance(newsuffix_by_prevtpl, dict):
                    suffix = newsuffix_by_prevtpl[self.previous_factory.tpl_by_setting_name[name]]
            suffixes.append(suffix)

        tpls = map(self._tpl, self.ctx.spec.settings)

        self.tpl_by_setting_name = {
            setting_name: SettingTuple(tpl, suffix)
            for setting_name, tpl, suffix in zip(setting_names, tpls, suffixes, strict=False)
        }

    @abstractmethod
    def _prototype(self, lookup_tuple) -> pe.Workflow:
        raise NotImplementedError()

    @abstractmethod
    def _tpl(self, setting) -> Hashable:
        raise NotImplementedError()

    def _should_skip(self, obj):
        return obj is None

    def _connect_inputs(self, hierarchy, inputnode, source_file, setting_name, _):
        if hasattr(inputnode.inputs, "repetition_time"):
            self.ctx.database.fillmetadata("repetition_time", [source_file])
            inputnode.inputs.repetition_time = self.ctx.database.metadata(source_file, "repetition_time")
        if hasattr(inputnode.inputs, "tags"):
            inputnode.inputs.tags = self.ctx.database.tags(source_file)
        self.previous_factory.connect(hierarchy, inputnode, source_file=source_file, setting_name=setting_name)

    def wf_factory(self, lookup_tuple: LookupTuple):
        if lookup_tuple not in self.wf_factories:
            logger.debug(f"Creating workflow with {self.__class__.__name__} for {lookup_tuple}")
            prototype = self._prototype(lookup_tuple)
            self.wf_factories[lookup_tuple] = deepcopyfactory(prototype)

            prototype_name = prototype.name
            assert isinstance(prototype_name, str)
            self.wf_names[lookup_tuple.setting_tuple] = prototype_name

        return self.wf_factories[lookup_tuple]()

    def get(self, source_file, setting_name):
        hierarchy = self._get_hierarchy("post_processing_wf", source_file=source_file)
        wf = hierarchy[-1]

        setting_tuple = self.tpl_by_setting_name[setting_name]
        lookup_tuple = LookupTuple(
            setting_tuple=setting_tuple,
            memcalc=MemoryCalculator.from_bold_file(source_file),
        )

        vwf = None
        if setting_tuple in self.wf_names:
            vwf = wf.get_node(self.wf_names[setting_tuple])
        connect_inputs = False

        if vwf is None:
            connect_inputs = True
            vwf = self.wf_factory(lookup_tuple)
            wf.add_nodes([vwf])

        assert isinstance(vwf, pe.Workflow)
        inputnode = vwf.get_node("inputnode")
        hierarchy.append(vwf)

        if connect_inputs:
            self._connect_inputs(hierarchy, inputnode, source_file, setting_name, lookup_tuple)

        outputnode = vwf.get_node("outputnode")

        return hierarchy, outputnode


class FmriprepAdapterFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        return init_fmriprep_adapter_wf(memcalc=lookup_tuple.memcalc)

    def _tpl(self, _) -> Hashable:
        return SettingTuple(value=None, suffix=None)

    def _connect_inputs(self, hierarchy, inputnode, source_file, setting_name, lookup_tuple: LookupTuple):
        super(FmriprepAdapterFactory, self)._connect_inputs(hierarchy, inputnode, source_file, setting_name, lookup_tuple)

        resample_hierarchy = self._get_hierarchy("fmriprep_24_2_wf", source_file=source_file)
        wf2 = resample_hierarchy[-1]
        ds_bold_std_wf = wf2.get_node("ds_bold_std_wf")
        bold_mask_std = ds_bold_std_wf.get_node("ds_mask")
        bold_std = ds_bold_std_wf.get_node("ds_bold")

        self.connect_attr(
            outputhierarchy=[*resample_hierarchy, ds_bold_std_wf],  # [*resample_hierarchy, bold_std],
            outputnode=bold_std,
            outattr="out_file",  # Bold_file
            inputhierarchy=hierarchy,
            inputnode=inputnode,
            inattr="bold_std",
        )

        self.connect_attr(
            outputhierarchy=[*resample_hierarchy, ds_bold_std_wf],
            outputnode=bold_mask_std,
            outattr="out_file",
            inputhierarchy=hierarchy,
            inputnode=inputnode,
            inattr="boldmask",
        )


class SmoothingFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        fwhm_value = setting_tuple.value

        if fwhm_value is None:
            fwhm = 0.0
        elif isinstance(fwhm_value, (float, int, str)):
            fwhm = float(fwhm_value)
        else:
            raise ValueError

        if fwhm <= 0 or isclose(fwhm, 0):
            return init_bypass_wf(attrs=["files", "mask", "vals"], name="no_smoothing_wf", suffix=suffix)

        return init_smoothing_wf(fwhm=fwhm, memcalc=lookup_tuple.memcalc, suffix=suffix)

    def _tpl(self, setting) -> Hashable:
        smoothing_dict = setting.get("smoothing")

        smoothing = None
        if isinstance(smoothing_dict, dict) and smoothing_dict.get("fwhm") is not None:
            fwhm = smoothing_dict["fwhm"]
            smoothing = f"{fwhm:f}"

        return smoothing


class GrandMeanScalingFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        mean = setting_tuple.value

        if mean is None:
            return init_bypass_wf(
                attrs=["files", "mask", "vals"],
                name="no_grand_mean_scaling_wf",
                suffix=suffix,
            )

        assert isinstance(mean, (float, int, str))
        mean = float(mean)

        return init_grand_mean_scaling_wf(mean=mean, memcalc=lookup_tuple.memcalc, suffix=suffix)

    def _tpl(self, setting) -> Hashable:
        grand_mean_scaling_dict = setting.get("grand_mean_scaling")

        grand_mean_scaling = None
        if isinstance(grand_mean_scaling_dict, dict) and grand_mean_scaling_dict.get("mean") is not None:
            mean = grand_mean_scaling_dict["mean"]
            grand_mean_scaling = f"{mean:f}"

        return grand_mean_scaling


class ICAAROMARegressionFactory(LookupFactory):
    def __init__(self, ctx, previous_factory, ica_aroma_components_factory):
        super(ICAAROMARegressionFactory, self).__init__(ctx, previous_factory)
        self.ica_aroma_components_factory = ica_aroma_components_factory

    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        ica_aroma = setting_tuple.value

        if ica_aroma is not True:
            return init_bypass_wf(
                attrs=["files", "mask", "vals"],
                name="no_ica_aroma_regression_wf",
                suffix=suffix,
            )

        return init_ica_aroma_regression_wf(
            workdir=str(self.ctx.workdir),
            memcalc=lookup_tuple.memcalc,
            suffix=suffix,
        )

    def _tpl(self, setting) -> Hashable:
        ica_aroma = setting.get("ica_aroma") is True
        return ica_aroma

    def _connect_inputs(self, hierarchy, inputnode, source_file, setting_name, lookup_tuple: LookupTuple):
        super(ICAAROMARegressionFactory, self)._connect_inputs(hierarchy, inputnode, source_file, setting_name, lookup_tuple)

        setting_tuple = lookup_tuple.setting_tuple
        ica_aroma = setting_tuple.value

        if ica_aroma is True:
            self.ica_aroma_components_factory.connect(hierarchy, inputnode, source_file=source_file, setting_name=setting_name)


class BandpassFilterFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple[BandpassFilterTuple]) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        bandpass_filter = setting_tuple.value

        if bandpass_filter is None:
            return init_bypass_wf(
                attrs=["files", "mask", "vals"],
                name="no_bandpass_filter_wf",
                suffix=suffix,
            )

        return init_bandpass_filter_wf(
            bandpass_filter=bandpass_filter,
            memcalc=lookup_tuple.memcalc,
            suffix=suffix,  # type: ignore
        )

    def _tpl(self, setting) -> Hashable:
        bandpass_filter_dict = setting.get("bandpass_filter")

        bandpass_filter = None
        if isinstance(bandpass_filter_dict, dict) and bandpass_filter_dict.get("type") is not None:
            if bandpass_filter_dict.get("type") == "gaussian":
                if bandpass_filter_dict.get("lp_width") is not None or bandpass_filter_dict.get("hp_width") is not None:
                    bandpass_filter = (
                        "gaussian",
                        bandpass_filter_dict.get("lp_width"),
                        bandpass_filter_dict.get("hp_width"),
                    )
            elif bandpass_filter_dict.get("type") == "frequency_based":
                if bandpass_filter_dict.get("low") is not None or bandpass_filter_dict.get("high") is not None:
                    bandpass_filter = (
                        "frequency_based",
                        bandpass_filter_dict.get("low"),
                        bandpass_filter_dict.get("high"),
                    )

        return bandpass_filter


class SettingAdapterFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix

        return init_setting_adapter_wf(suffix=suffix)

    def _tpl(self, _) -> Hashable:
        return None


class ConfoundsSelectFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        confound_names = setting_tuple.value

        if confound_names is None:
            return init_bypass_wf(
                attrs=["bold", "confounds", "mask", "vals"],
                unconnected_attrs=["confounds_matrix"],
                name="no_confounds_select_wf",
                suffix=suffix,
            )

        assert isinstance(confound_names, (list, tuple))
        return init_confounds_select_wf(confound_names=list(confound_names), suffix=suffix)

    def _tpl(self, setting) -> Hashable:
        confounds_removal = setting.get("confounds_removal")

        confound_names = None
        if confounds_removal is not None and len(confounds_removal) > 0:
            confound_names = tuple(sorted(confounds_removal))

        return confound_names


class ConfoundsRegressionFactory(LookupFactory):
    def _prototype(self, lookup_tuple: LookupTuple) -> pe.Workflow:
        setting_tuple = lookup_tuple.setting_tuple
        suffix = setting_tuple.suffix
        has_confounds = setting_tuple.value

        if has_confounds is not True:
            return init_bypass_wf(
                attrs=["bold", "confounds_selected", "confounds", "mask", "vals"],
                name="no_confounds_regression_wf",
                suffix=suffix,
            )

        return init_confounds_regression_wf(memcalc=lookup_tuple.memcalc, suffix=suffix)

    def _tpl(self, setting) -> Hashable:
        confounds_removal = setting.get("confounds_removal")

        has_confounds = False
        if confounds_removal is not None and len(confounds_removal) > 0:
            has_confounds = True

        return has_confounds


class PostProcessingFactory(Factory):
    def __init__(self, ctx: FactoryContext, fmriprep_factory: FmriprepFactory) -> None:
        super().__init__(ctx)
        """
        Through this init function we decide what information/variables are available in each factory.
        This generates a sequential dependency between the factories, because the LookUp factory class
        always checks the previous factory.
        Practically, this defines order of our own processing steps.
        """

        self.fmriprep_factory = fmriprep_factory

        self.alt_bold_factory = AltBOLDFactory(ctx, self.fmriprep_factory)
        self.ica_aroma_components_factory = ICAAROMAComponentsFactory(ctx, self.fmriprep_factory, self.alt_bold_factory)
        self.fmriprep_adapter_factory = FmriprepAdapterFactory(ctx, self.fmriprep_factory)
        self.smoothing_factory = SmoothingFactory(ctx, self.fmriprep_adapter_factory)
        self.grand_mean_scaling_factory = GrandMeanScalingFactory(ctx, self.smoothing_factory)
        self.ica_aroma_regression_factory = ICAAROMARegressionFactory(
            ctx, self.grand_mean_scaling_factory, self.ica_aroma_components_factory
        )
        self.bandpass_filter_factory = BandpassFilterFactory(ctx, self.ica_aroma_regression_factory)

        self.setting_adapter_factory = SettingAdapterFactory(ctx, self.bandpass_filter_factory)
        self.confounds_select_factory = ConfoundsSelectFactory(ctx, self.setting_adapter_factory)
        self.confounds_regression_factory = ConfoundsRegressionFactory(ctx, self.confounds_select_factory)

        setting_names = set(setting["name"] for setting in self.ctx.spec.settings if setting.get("output_image") is True)
        self.source_files = self.get_source_files(setting_names)

    def get_source_files(self, setting_names) -> set[str]:
        bold_file_paths = set(self.ctx.database.get(datatype="func", suffix="bold"))
        source_files: set[str] = set()
        for setting in self.ctx.spec.settings:
            if setting.get("name") in setting_names:
                filters = setting.get("filters")
                if filters is None or len(filters) == 0:
                    return bold_file_paths
                else:
                    source_files |= self.ctx.database.applyfilters(bold_file_paths, filters)
        return source_files

    def setup(self, raw_sources_dict: dict | None = None) -> None:
        if raw_sources_dict is None:
            raw_sources_dict = dict()

        self.alt_bold_factory.setup()
        self.ica_aroma_components_factory.setup()
        self.fmriprep_adapter_factory.setup()
        self.smoothing_factory.setup()
        self.grand_mean_scaling_factory.setup()
        self.ica_aroma_regression_factory.setup()
        self.bandpass_filter_factory.setup()

        self.setting_adapter_factory.setup()
        self.confounds_select_factory.setup()
        self.confounds_regression_factory.setup()

        for setting in self.ctx.spec.settings:
            setting_output_wf_factory = deepcopyfactory(
                init_setting_output_wf(workdir=str(self.ctx.workdir), setting_name=setting["name"])
            )

            if setting.get("output_image") is not True:
                continue  # create lazily in FeatureFactory

            source_files = set(raw_sources_dict.keys())

            filters = setting.get("filters")
            if filters is not None and len(filters) > 0:
                source_files = self.ctx.database.applyfilters(source_files, filters)

            for source_file in source_files:
                hierarchy = self._get_hierarchy("post_processing_wf", source_file=source_file)

                wf = setting_output_wf_factory()
                hierarchy[-1].add_nodes([wf])
                hierarchy.append(wf)

                inputnode = wf.get_node("inputnode")

                tags: dict[str, str] = dict(setting=setting["name"])

                source_file_tags = self.ctx.database.tags(source_file)
                assert isinstance(source_file_tags, dict)
                tags.update(source_file_tags)

                inputnode.inputs.tags = tags

                metadata = collect_metadata(self.ctx.database, source_file, setting)
                if raw_sources_dict.get(source_file) is not None:
                    metadata["raw_sources"] = raw_sources_dict.get(source_file)
                inputnode.inputs.metadata = metadata

                self.connect(
                    hierarchy,
                    inputnode,
                    source_file,
                    setting_name=setting["name"],
                    confounds_action="regression",
                )

    def get(self, source_file, setting_name, confounds_action=None):
        # self.fmriprep_adapter_factory.get(source_file)
        if self.ctx.spec.global_settings["run_aroma"] is True:
            # Make sure ica aroma components are calculated when enabled
            # The component calculation is independent from the noise components regression application
            # so we generally ran components by default and apply them if the specific settings of spec file
            # shows "ica_aroma=True"
            self.ica_aroma_components_factory.get(source_file)
        if confounds_action == "select":
            return self.confounds_select_factory.get(source_file, setting_name)
        elif confounds_action == "regression":
            return self.confounds_regression_factory.get(source_file, setting_name)
        elif confounds_action is None:
            return self.setting_adapter_factory.get(source_file, setting_name)
        else:
            raise ValueError(f"Unknown counfounds action '{confounds_action}'")
