# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from halfpipe import resource

# Refactor

test_online_resources = {
    "wakemandg_hensonrn_statmaps.tar.gz": "https://figshare.com/ndownloader/files/25621988",
    "ds000108fixed.tar.gz": "https://osf.io/download/qh38c",
    "bids_data.zip": "https://figshare.com/ndownloader/files/48018256",  # original url "https://osf.io/download/qrvu4"
    "PNAS_Smith09_rsn10.nii.gz": "https://www.nitrc.org/frs/download.php/7729/PNAS_Smith09_rsn10.nii.gz",
    "HarvardOxford.tgz": "https://www.nitrc.org/frs/download.php/9902/HarvardOxford.tgz",
    "run_01_spmdef.mat": "ftp://ftp.mrc-cbu.cam.ac.uk/personal/rik.henson/wakemandg_hensonrn/Sub01/BOLD/Trials/run_01_spmdef.mat",
    "sub-50005_task-rest_Atlas_s0.dtseries.nii": "https://github.com/edickie/ciftify/raw/v2.1.0/tests/data/sub-50005_task-rest_Atlas_s0.dtseries.nii",
    "sub-50005.L.midthickness.32k_fs_LR.surf.gii": "https://raw.githubusercontent.com/edickie/ciftify/v2.1.0/tests/data/sub-50005.L.midthickness.32k_fs_LR.surf.gii",
    "sub-50005.R.midthickness.32k_fs_LR.surf.gii": "https://raw.githubusercontent.com/edickie/ciftify/v2.1.0/tests/data/sub-50005.R.midthickness.32k_fs_LR.surf.gii",
    "sub-50005_task-rest_bold_space-MNI152NLin2009cAsym_preproc.nii.gz": "https://github.com/edickie/ciftify/raw/v2.1.0/tests/data/sub-50005_task-rest_bold_space-MNI152NLin2009cAsym_preproc.nii.gz",
    "tpl-MNI152NLin2009cAsym_atlas-DiFuMo_desc-1024dimensions_probseg.tsv": "https://download.fmri.science/test_resources/tpl-MNI152NLin2009cAsym_atlas-DiFuMo_desc-1024dimensions_probseg.tsv",
    "tpl-MNI152NLin2009cAsym_res-02_atlas-DiFuMo_desc-1024dimensions_probseg.nii.gz": "https://download.fmri.science/test_resources/tpl-MNI152NLin2009cAsym_res-02_atlas-DiFuMo_desc-1024dimensions_probseg.nii.gz",
    "sub-0003_fmriprep_derivatives.zip": "https://download.fmri.science/test_resources/sub-0003_fmriprep_derivatives.zip",
    "atlases.zip": "https://github.com/HALFpipe/Atlases/releases/download/1.0.1/atlases.zip",
    "bad_quaternion.nii.gz": "https://github.com/spinalcordtoolbox/spinalcordtoolbox/files/8492834/bad_quaternion.nii.gz",
}


def setup():
    resource.online_resources.update(test_online_resources)
