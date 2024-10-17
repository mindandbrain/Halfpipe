# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from pathlib import Path
from unittest.mock import patch

from fmriprep import config
from fmriprep.cli.workflow import build_workflow
from nipype.interfaces.base.traits_extension import isdefined
from nipype.pipeline import engine as pe

from ..collect.fmap import collect_fieldmaps
from ..logging import logger
from ..utils.copy import deepcopyfactory
from ..utils.format import inflect_engine as p
from .constants import Constants
from .factory import Factory
from .memory import MemoryCalculator
from .reports import init_anat_report_wf, init_func_report_wf


def _find_input(hierarchy, node, attr):
    wf = hierarchy[-1]
    for u, _, datadict in wf._graph.in_edges(nbunch=node, data=True):
        for in_attr, out_attr in datadict["connect"]:
            if out_attr == attr:
                return hierarchy, u, in_attr
    raise ValueError()


def _find_child(hierarchy, name):
    wf = hierarchy[-1]
    for node in wf._graph.nodes():
        if node.name == name:
            return hierarchy, node
        elif isinstance(node, pe.Workflow):
            res = _find_child([*hierarchy, node], name)
            if res is not None:
                return res


class FmriprepFactory(Factory):
    def __init__(self, ctx):
        super(FmriprepFactory, self).__init__(ctx)

    def setup(self, workdir, bold_file_paths: set[str]) -> set[str]:
        spec = self.ctx.spec
        database = self.ctx.database
        bids_database = self.ctx.bids_database
        workflow = self.ctx.workflow

        uuidstr = str(workflow.uuid)[:8]
        bids_dir = Path(workdir) / "rawdata"

        # init fmriprep config
        output_dir = Path(workdir) / "derivatives"
        output_dir.mkdir(parents=True, exist_ok=True)

        fmriprep_dir = output_dir / "fmriprep"
        fmriprep_dir.mkdir(parents=True, exist_ok=True)

        subjects = set()
        bids_subjects = set()
        for bold_file_path in bold_file_paths:
            subject = database.tagval(bold_file_path, "sub")

            if subject is None:
                continue

            bids_path = bids_database.to_bids(bold_file_path)
            assert bids_path is not None
            bids_subject = bids_database.get_tag_value(bids_path, "subject")

            if bids_subject is None:
                continue

            subjects.add(subject)
            bids_subjects.add(bids_subject)

        global_settings = spec.global_settings

        ignore = []
        if global_settings["slice_timing"] is not True:
            ignore.append("slicetiming")

        skull_strip_t1w = {
            "none": "skip",
            "auto": "auto",
            "ants": "force",
        }[global_settings["skull_strip_algorithm"]]

        # reset fmriprep config
        config.execution.bids_database_dir = None
        config.execution._layout = None
        config.execution.layout = None

        output_spaces = [f"{Constants.reference_space}:res-{Constants.reference_res}:cohort-2"]

        if global_settings["run_reconall"]:
            output_spaces.append("fsaverage:den-164k")
            output_spaces.append("fsnative")

        # create config
        config.from_dict(
            {
                #
                "bids_dir": bids_dir,  # input directory
                "output_dir": output_dir,  # derivatives folder
                "fmriprep_dir": fmriprep_dir,  # fmriprep subfolder
                "log_dir": str(workdir),  # put crash files directly in working directory
                "work_dir": str(workdir / ".fmriprep"),  # where toml configuration files will go
                "output_layout": "legacy",  # do not yet use the new layout
                "participant_label": sorted(bids_subjects),  # include all subjects
                "write_graph": global_settings["write_graph"],
                # smriprep config
                "anat_only": global_settings["anat_only"],
                "skull_strip_t1w": skull_strip_t1w,
                "skull_strip_fixed_seed": global_settings["skull_strip_fixed_seed"],
                "skull_strip_template": global_settings["skull_strip_template"],
                # freesurfer config
                "run_reconall": global_settings["run_reconall"],
                "hires": global_settings["hires"],
                "cifti_output": False,  # we do this in halfpipe
                "t2s_coreg": global_settings["t2s_coreg"],
                "medial_surface_nan": global_settings["medial_surface_nan"],
                "longitudinal": global_settings["longitudinal"],
                #
                "dummy_scans": global_settings["dummy_scans"],  # remove initial non-steady state volumes
                # bold_reg_wf config
                "use_bbr": global_settings["use_bbr"],
                "bold2t1w_dof": global_settings["bold2t1w_dof"],
                # sdcflows config
                "fmap_bspline": global_settings["fmap_bspline"],
                "force_syn": global_settings["force_syn"],
                #
                "ignore": ignore,  # used to disable slice timing
                # ica_aroma_wf settings
                "use_aroma": False,  # we do this in halfpipe
                "aroma_err_on_warn": global_settings["aroma_err_on_warn"],
                "aroma_melodic_dim": global_settings["aroma_melodic_dim"],
                #
                "regressors_all_comps": global_settings["regressors_all_comps"],
                "regressors_dvars_th": global_settings["regressors_dvars_th"],
                "regressors_fd_th": global_settings["regressors_fd_th"],
                #
                "output_spaces": " ".join(output_spaces),
                #
                "sloppy": global_settings["sloppy"],  # used for unit testing
            }
        )
        nipype_dir = Path(workdir) / Constants.workflow_directory
        nipype_dir.mkdir(parents=True, exist_ok=True)
        config_file = nipype_dir / f"fmriprep.config.{uuidstr}.toml"
        config.to_filename(config_file)

        retval: dict[str, pe.Workflow] = dict()

        with patch("niworkflows.utils.misc.check_valid_fs_license") as mock:
            mock.return_value = True
            build_workflow(config_file, retval)

        fmriprep_wf = retval["workflow"]
        assert isinstance(fmriprep_wf, pe.Workflow)
        workflow.add_nodes([fmriprep_wf])

        # check and patch workflow
        skipped = set()
        for bold_file_path in bold_file_paths:
            func_preproc_wf = self._get_hierarchy("fmriprep_wf", source_file=bold_file_path)[-1]

            if not isinstance(func_preproc_wf, pe.Workflow) or len(func_preproc_wf._graph) == 0:
                logger.warning(f'fMRIPrep skipped processing for file "{bold_file_path}"')
                skipped.add(bold_file_path)
                continue

            if len(collect_fieldmaps(database, bold_file_path, silent=True)) > 0:  # has fieldmaps
                if func_preproc_wf.get_node("sdc_estimate_wf") is None:
                    logger.warning(f'fMRIPrep did not detect field maps for file "{bold_file_path}"')

            if global_settings["slice_timing"] is True:
                if func_preproc_wf.get_node("bold_stc_wf") is None:
                    logger.warning(f'fMRIPrep did not find slice timing metadata for file "{bold_file_path}"')

            # disable preproc output to save disk space
            func_derivatives_wf = func_preproc_wf.get_node("func_derivatives_wf")
            assert isinstance(func_derivatives_wf, pe.Workflow)
            for name in ["ds_bold_surfs", "ds_bold_std"]:
                node = func_derivatives_wf.get_node(name)
                if isinstance(node, pe.Node):
                    func_derivatives_wf.remove_nodes([node])

            # patch memory usage
            memcalc = MemoryCalculator.from_bold_file(bold_file_path)
            for node in func_preproc_wf._get_all_nodes():
                memcalc.patch_mem_gb(node)

        bold_file_paths -= skipped

        # halfpipe-specific report workflows
        anat_report_wf_factory = deepcopyfactory(init_anat_report_wf(workdir=str(workdir)))
        for subject_id in subjects:
            hierarchy = self._get_hierarchy("reports_wf", subject_id=subject_id)

            wf = anat_report_wf_factory()
            hierarchy[-1].add_nodes([wf])
            hierarchy.append(wf)

            inputnode = wf.get_node("inputnode")
            inputnode.inputs.tags = {"sub": subject_id}

            self.connect(hierarchy, inputnode, subject_id=subject_id)

        for bold_file_path in bold_file_paths:
            hierarchy = self._get_hierarchy("reports_wf", source_file=bold_file_path)

            wf = init_func_report_wf(
                workdir=str(workdir),
                memcalc=MemoryCalculator.from_bold_file(bold_file_path),
            )
            assert wf.name == "func_report_wf"  # check name for line 206
            hierarchy[-1].add_nodes([wf])
            hierarchy.append(wf)

            inputnode = wf.get_node("inputnode")
            assert isinstance(inputnode, pe.Node)
            inputnode.inputs.tags = database.tags(bold_file_path)
            inputnode.inputs.fd_thres = global_settings["fd_thres"]

            inputnode.inputs.repetition_time = database.metadata(bold_file_path, "repetition_time")
            self.connect(hierarchy, inputnode, source_file=bold_file_path)

        return bold_file_paths

    def get(self, *args, **kwargs):
        raise NotImplementedError

    def connect(self, nodehierarchy, node, source_file=None, subject_id=None, **_) -> None:
        """
        connect equally names attrs
        preferentially use datasinked outputs
        """

        connected_attrs: set[str] = set()

        inputattrs = set(node.inputs.copyable_trait_names())
        dsattrs = set(attr for attr in inputattrs if attr.startswith("ds_"))

        for key, value in node.inputs.get().items():
            if isdefined(value):
                inputattrs.remove(key)

        ignore = frozenset(["alt_bold_mask_std", "alt_bold_std", "alt_spatial_reference"])
        inputattrs -= ignore

        def _connect(hierarchy) -> None:
            wf = hierarchy[-1]

            outputnode: pe.Node | None = wf.get_node("outputnode")
            if outputnode is not None:
                outputattrs = set(outputnode.outputs.copyable_trait_names())
                attrs = (inputattrs & outputattrs) - connected_attrs  # find common attr names

                actually_connected_attrs: set[str] = set()
                for _, _, datadict in wf._graph.in_edges(outputnode, data=True):
                    _, infields = zip(*datadict.get("connect", []), strict=False)
                    actually_connected_attrs.update(infields)

                for key, value in outputnode.inputs.get().items():
                    if isdefined(value):
                        actually_connected_attrs.add(key)

                attrs &= actually_connected_attrs

                for attr in attrs:
                    self.connect_attr(hierarchy, outputnode, attr, nodehierarchy, node, attr)
                    connected_attrs.add(attr)

            for attr in list(dsattrs):
                childtpl = _find_child(hierarchy, attr)
                if childtpl is not None:
                    childhierarchy, childnode = childtpl
                    childhierarchy, childnode, childattr = _find_input(childhierarchy, childnode, "in_file")
                    self.connect_attr(childhierarchy, childnode, childattr, nodehierarchy, node, attr)
                    dsattrs.remove(attr)
                    connected_attrs.add(attr)

        hierarchy = self._get_hierarchy("fmriprep_wf", source_file=source_file, subject_id=subject_id)

        wf = hierarchy[-1]

        # anat only
        anat_wf = wf.get_node("anat_preproc_wf")

        if anat_wf is None:
            # func first
            _connect(hierarchy)

            if "skip_vols" in inputattrs:
                initial_boldref_wf = wf.get_node("initial_boldref_wf")
                assert isinstance(initial_boldref_wf, pe.Workflow)
                outputnode = initial_boldref_wf.get_node("outputnode")
                self.connect_attr(
                    [*hierarchy, initial_boldref_wf],
                    outputnode,
                    "skip_vols",
                    nodehierarchy,
                    node,
                    "skip_vols",
                )
                connected_attrs.add("skip_vols")

            for name in [
                "bold_bold_trans_wf",
                "bold_hmc_wf",
                "final_boldref_wf",
                "bold_reg_wf",
                "sdc_estimate_wf",
                "sdc_bypass_wf",
                "sdc_unwarp_report_wf",
                "bold_std_trans_wf",
                "bold_surf_wf",
                "bold_confounds_wf",
            ]:
                bold_wf = wf.get_node(name)
                if bold_wf is not None:
                    _connect([*hierarchy, bold_wf])

            if "bold_split" in inputattrs:
                splitnode = wf.get_node("split_opt_comb")
                if splitnode is None:
                    splitnode = wf.get_node("bold_split")
                self.connect_attr(hierarchy, splitnode, "out_files", nodehierarchy, node, "bold_split")
                connected_attrs.add("bold_split")

            report_hierarchy = self._get_hierarchy("reports_wf", source_file=source_file, subject_id=subject_id)
            func_report_wf = report_hierarchy[-1].get_node("func_report_wf")  # this is not part of fmriprep
            if func_report_wf is not None:
                _connect([*report_hierarchy, func_report_wf])

            while wf.get_node("anat_preproc_wf") is None:
                hierarchy.pop()
                wf = hierarchy[-1]

            anat_wf = wf.get_node("anat_preproc_wf")

        assert isinstance(anat_wf, pe.Workflow)
        for name in ["anat_norm_wf", "anat_reports_wf"]:
            wf = anat_wf.get_node(name)
            _connect([*hierarchy, anat_wf, wf])
        _connect([*hierarchy, anat_wf])

        if connected_attrs != inputattrs:
            missing_attrs: list[str] = sorted(inputattrs - connected_attrs)
            logger.info(f"Unable to find fMRIPrep outputs {p.join(missing_attrs)} " f"for workflow {nodehierarchy}")

        return
