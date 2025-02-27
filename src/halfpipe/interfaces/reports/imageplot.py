# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from os import path as op
from uuid import uuid4

import nibabel as nib
import numpy as np
from matplotlib import colormaps
from nilearn.plotting import plot_anat, plot_epi
from nipype.interfaces.base import File, isdefined, traits

try:
    from nireports.interfaces.reporting.base import (
        ReportingInterface,
        _SVGReportCapableInputSpec,
    )
except ImportError:
    from niworkflows.interfaces.report_base import (
        ReportingInterface,
        _SVGReportCapableInputSpec,
    )

from niworkflows.viz.utils import (
    compose_view,
    cuts_from_bbox,
    extract_svg,
    robust_set_limits,
)
from seaborn import color_palette
from svgutils.transform import fromstring

from ...resource import get as getresource
from ...utils.image import nvol


def robust_set_limits_in_mask(data_img: nib.analyze.AnalyzeImage, mask_img: nib.analyze.AnalyzeImage) -> dict[str, float]:
    plot_params: dict[str, float] = dict()

    mask = np.asanyarray(mask_img.dataobj).astype(bool)
    data = data_img.get_fdata()[mask]
    plot_params = robust_set_limits(data.reshape(-1), plot_params)

    return plot_params


class PlotInputSpec(_SVGReportCapableInputSpec):
    in_file = File(exists=True, mandatory=True, desc="volume")
    mask_file = File(exists=True, mandatory=True, desc="mask")
    label = traits.Str()


class PlotEpi(ReportingInterface):
    input_spec = PlotInputSpec

    def _generate_report(self):
        epi_img = nib.nifti1.load(self.inputs.in_file)
        mask_img = nib.nifti1.load(self.inputs.mask_file)
        assert nvol(epi_img) == 1
        assert nvol(mask_img) == 1

        label = None
        if isdefined(self.inputs.label):
            label = self.inputs.label

        compress = self.inputs.compress_report

        n_cuts = 7
        cuts = cuts_from_bbox(mask_img, cuts=n_cuts)

        plot_params = robust_set_limits_in_mask(epi_img, mask_img)

        outfiles = []
        for dimension in ["z", "y", "x"]:
            display = plot_epi(
                epi_img,
                draw_cross=False,
                display_mode=dimension,
                cut_coords=cuts[dimension],
                title=label,
                colorbar=(dimension == "z"),
                cmap=colormaps.get_cmap("gray"),
                **plot_params,
            )

            display.add_contours(mask_img, levels=[0.5], colors="r")

            label = None  # only on first

            svg = extract_svg(display, compress=compress)
            svg = svg.replace("figure_1", str(uuid4()), 1)

            outfiles.append(fromstring(svg))

        self._out_report = op.abspath(self.inputs.out_report)
        compose_view(bg_svgs=outfiles, fg_svgs=None, out_file=self._out_report)


class PlotRegistrationInputSpec(PlotInputSpec):
    template = traits.Str(mandatory=True)


class PlotRegistration(ReportingInterface):
    input_spec = PlotRegistrationInputSpec

    def _generate_report(self):
        anat_img = nib.nifti1.load(self.inputs.in_file)
        mask_img = nib.nifti1.load(self.inputs.mask_file)
        assert nvol(anat_img) == 1
        assert nvol(mask_img) == 1

        plot_params = robust_set_limits_in_mask(anat_img, mask_img)

        template = self.inputs.template
        parc_file = getresource(f"tpl-{template}_RegistrationCheckOverlay.nii.gz")
        assert parc_file is not None
        parc_img = nib.nifti1.load(parc_file)

        levels = np.unique(np.asanyarray(parc_img.dataobj).astype(np.int32))
        levels = (levels[levels > 0] - 0.5).tolist()
        colors = color_palette("husl", len(levels))

        label = None
        if isdefined(self.inputs.label):
            label = self.inputs.label

        compress = self.inputs.compress_report

        n_cuts = 7
        cuts = cuts_from_bbox(mask_img, cuts=n_cuts)

        outfiles = []
        for dimension in ["z", "y", "x"]:
            display = plot_anat(
                anat_img,
                draw_cross=False,
                display_mode=dimension,
                cut_coords=cuts[dimension],
                title=label,
                **plot_params,
            )

            display.add_contours(parc_img, levels=levels, colors=colors, linewidths=0.25)
            display.add_contours(mask_img, levels=[0.5], colors="r", linewidths=0.5)

            label = None  # only on first

            svg = extract_svg(display, compress=compress)
            svg = svg.replace("figure_1", str(uuid4()), 1)

            outfiles.append(fromstring(svg))

        self._out_report = op.abspath(self.inputs.out_report)
        compose_view(bg_svgs=outfiles, fg_svgs=None, out_file=self._out_report)
