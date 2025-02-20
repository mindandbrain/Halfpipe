################################
 Welcome to ENIGMA ``HALFpipe``
################################

.. image:: https://github.com/HALFpipe/HALFpipe/actions/workflows/continuous_integration.yml/badge.svg
   :target: https://github.com/HALFpipe/HALFpipe/actions/workflows/continuous_integration.yml

.. image:: https://codecov.io/gh/HALFpipe/HALFpipe/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/HALFpipe/HALFpipe

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.5657185.svg
   :target: https://doi.org/10.5281/zenodo.5657185

``HALFpipe`` is a user-friendly software that facilitates reproducible
analysis of fMRI data, including preprocessing, single-subject, and
group analysis. It provides state-of-the-art preprocessing using
`fmriprep <https://fmriprep.readthedocs.io/>`__, but removes the
necessity to convert data to the `BIDS
<https://bids-specification.readthedocs.io/en/stable/>`__ format. Common
resting-state and task-based fMRI features can then be calculated on the
fly.

`HALFpipe` relies on tools from well-established neuroimaging software
packages, either directly or through our dependencies, including `ANTs
<https://antspy.readthedocs.io/>`__, `FreeSurfer
<https://surfer.nmr.mgh.harvard.edu/>`__,  `FSL <http://fsl.fmrib.ox.ac.uk/>`__,
`AFNI <https://afni.nimh.nih.gov/>`__ and `nipype <https://nipype.readthedocs.io/>`__.
We strongly urge users to acknowledge these tools when publishing results obtained
with HALFpipe.

   Subscribe to our `mailing list <https://mailman.charite.de/mailman/listinfo/halfpipe-announcements>`_ to stay up to date with new developments and releases.

..

   If you encounter issues, please see the `troubleshooting
   <#troubleshooting>`__ section of this document.

..

   Some sections of this document are marked as outdated. While we are
   working on updating them, the `paper <https://doi.org/hmts>`__
   and the `analysis manual
   <https://docs.google.com/document/d/108-XBIuwtJziRVVdOQv73MRgtK78wfc-NnVu-jSc9oI/edit#heading=h.3y6rt7h7o483>`__
   should be able to answer most questions.

*******************
 Table of Contents
*******************

.. raw:: html

   <!-- toc -->

-  `Getting started <#getting-started>`__

   -  `Container platform <#container-platform>`__
   -  `Download <#download>`__
   -  `Running <#running>`__

-  `User interface <#user-interface>`__

   -  `Files <#files>`__
   -  `Features <#features>`__
   -  `Models <#models>`__

-  `Running on a high-performance computing cluster
   <#running-on-a-high-performance-computing-cluster>`__

-  `Quality checks <#quality-checks>`__

-  `Outputs <#outputs>`__

   -  `Subject-level features <#subject-level-features>`__
   -  `Preprocessed images <#preprocessed-images>`__
   -  `Group-level <#group-level>`__

-  `Troubleshooting <#troubleshooting>`__

-  `Command line flags <#command-line-flags>`__

   -  `Control command line logging <#control-command-line-logging>`__
   -  `Automatically remove unneeded files
      <#automatically-remove-unneeded-files>`__
   -  `Adjust nipype <#adjust-nipype>`__
   -  `Choose which parts to run or to skip
      <#choose-which-parts-to-run-or-to-skip>`__
   -  `Working directory <#working-directory>`__
   -  `Data file system root <#data-file-system-root>`__

-  `Contact <#contact>`__

.. raw:: html

   <!-- tocstop -->

*****************
 Getting started
*****************

``HALFpipe`` is distributed as a container, meaning that all required
software comes bundled in a monolithic file, the container. This allows
for easy installation on new systems, and makes data analysis more
reproducible, because software versions are guaranteed to be the same
for all users.

Container platform
==================

The first step is to install one of the supported container platforms.
If you’re using a high-performance computing cluster, more often than
not `Singularity <https://sylabs.io>`__ will already be available.

If not, we recommend using the latest version of\ `Singularity
<https://sylabs.io>`__. However, it can be somewhat cumbersome to
install, as it needs to be built from source.

The `NeuroDebian <https://neuro.debian.net/>`__ package repository
provides an older version of `Singularity
<https://sylabs.io/guides/2.6/user-guide/>`__ for `some
<https://neuro.debian.net/pkgs/singularity-container.html>`__ Linux
distributions.

If you are running ``mac OS``, then you should be able to run the
container with ``Docker Desktop``.

If you are running Windows, you can also try running with ``Docker
Desktop``, but we have not done any compatibility testing yet, so issues
may occur, for example with respect to file systems.

.. list-table::
   :header-rows: 1

   -  -  Container platform
      -  Version
      -  Installation

   -  -  Singularity
      -  3.x
      -  https://sylabs.io/guides/3.8/user-guide/quick_start.html

   -  -  Singularity
      -  2.x
      -  ``sudo apt install singularity-container``

   -  -  Docker
      -  ..
      -  See https://docs.docker.com/engine/install/

Download
========

The second step is to download the ``HALFpipe`` to your computer. This
requires approximately 5 gigabytes of storage.

.. list-table::
   :header-rows: 1

   -  -  Container platform
      -  Version
      -  Installation

   -  -  Singularity
      -  3.x
      -  https://download.fmri.science/singularity/halfpipe-latest.sif

   -  -  Singularity
      -  2.x
      -  https://download.fmri.science/singularity/halfpipe-latest.simg

   -  -  Docker
      -  ..
      -  ``docker pull halfpipe/halfpipe:latest``

``Singularity`` version ``3.x`` creates a container image file called
``HALFpipe_{version}.sif`` in the directory where you run the ``pull``
command. For ``Singularity`` version ``2.x`` the file is named
``halfpipe-halfpipe-master-latest.simg``. Whenever you want to use the
container, you need pass ``Singularity`` the path to this file.

   **NOTE:** ``Singularity`` may store a copy of the container in its
   cache directory. The cache directory is located by default in your
   home directory at ``~/.singularity``. If you need to save disk space
   in your home directory, you can safely delete the cache directory
   after downloading, i.e. by running ``rm -rf ~/.singularity``.
   Alternatively, you could move the cache directory somewhere with more
   free disk space using a symlink. This way, files will automatically
   be stored there in the future. For example, if you have a lot of free
   disk space in ``/mnt/storage``, then you could first run ``mv
   ~/.singularity /mnt/storage`` to move the cache directory, and then
   ``ln -s /mnt/storage/.singularity ~/.singularity`` to create the
   symlink.

``Docker`` will store the container in its storage base directory, so it
does not matter from which directory you run the ``pull`` command.

Running
=======

The third step is to run the downloaded container. You may need to
replace ``halfpipe-halfpipe-latest.simg`` with the actual path and
filename where ``Singularity`` downloaded your container.

.. list-table::
   :header-rows: 1

   -  -  Container platform
      -  Command

   -  -  Singularity
      -  ``singularity run --containall --bind /:/ext
         halfpipe-halfpipe-latest.simg``

   -  -  Docker
      -  ``docker run --interactive --tty --volume /:/ext
         halfpipe/halfpipe``

You should now see the user interface.

Background
----------

Containers are by default isolated from the host computer. This adds
security, but also means that the container cannot access the data it
needs for analysis. ``HALFpipe`` expects all inputs (e.g., image files
and spreadsheets) and outputs (the working directory) to be places in
the path\ ``/ext`` (see also ```--fs-root``
<#data-file-system-root---fs-root>`__). Using the option ``--bind
/:/ext``, we instruct ``Singularity`` to map all of the host file system
(``/``) to that path (``/ext``). You can also run ``HALFpipe`` and only
map only part of the host file system, but keep in mind that any
directories that are not mapped will not be visible later.

``Singularity`` passes the host shell environment to the container by
default. This means that in some cases, the host computer’s
configuration can interfere with the software. To avoid this, we need to
pass the option ``--containall``. ``Docker`` does not pass the host
shell environment by default, so we don’t need to pass an option.

****************
 User interface
****************

   Outdated

The user interface asks a series of questions about your data and the
analyses you want to run. In each question, you can press ``Control+C``
to cancel the current question and go back to the previous one.
``Control+D`` exits the program without saving. Note that these keyboard
shortcuts are the same on Mac.

Files
=====

To run preprocessing, at least a T1-weighted structural image and a BOLD
image file is required. Preprocessing and data analysis proceeds
automatically. However, to be able to run automatically, data files need
to be input in a way suitable for automation.

For this kind of automation, ``HALFpipe`` needs to know the
relationships between files, such as which files belong to the same
subject. However, even though it would be obvious for a human, a program
cannot easily assign a file name to a subject, and this will be true as
long as there are differences in naming between different researchers or
labs. One researcher may name the same file ``subject_01_rest.nii.gz``
and another ``subject_01/scan_rest.nii.gz``.

In ``HALFpipe``, we solve this issue by inputting file names in a
specific way. For example, instead of ``subject_01/scan_rest.nii.gz``,
``HALFpipe`` expects you to input ``{subject}/scan_rest.nii.gz``.
``HALFpipe`` can then match all files on disk that match this naming
schema, and extract the subject ID ``subject_01``. Using the extracted
subject ID, other files can now be matched to this image. If all input
files are available in BIDS format, then this step can be skipped.

#. ``Specify working directory`` All intermediate and outputs of
   ``HALFpipe`` will be placed in the working directory. Keep in mind to
   choose a location with sufficient free disk space, as intermediates
   can be multiple gigabytes in size for each subject.

#. ``Is the data available in BIDS format?``

   -  ``Yes``

      #. ``Specify the path of the BIDS directory``

   -  ``No``

      #. ``Specify anatomical/structural data`` ``Specify the path of
         the T1-weighted image files``

      #. ``Specify functional data`` ``Specify the path of the BOLD
         image files``

      #. ``Check repetition time values`` / ``Specify repetition time in
         seconds``

      #. ``Add more BOLD image files?``

         -  ``Yes`` Loop back to 2
         -  ``No`` Continue

#. ``Do slice timing?``

   -  ``Yes``

      #. ``Check slice acquisition direction values``
      #. ``Check slice timing values``

   -  ``No`` Skip this step

#. ``Specify field maps?`` If the data was imported from a BIDS
   directory, this step will be omitted.

   -  ``Yes``

      #. ``Specify the type of the field maps``

         -  EPI (blip-up blip-down)

            #. ``Specify the path of the blip-up blip-down EPI image
               files``

         -  Phase difference and magnitude (used by Siemens scanners)

            #. ``Specify the path of the magnitude image files``
            #. ``Specify the path of the phase/phase difference image
               files``
            #. ``Specify echo time difference in seconds``

         -  Scanner-computed field map and magnitude (used by GE /
            Philips scanners)

            #. ``Specify the path of the magnitude image files``
            #. ``Specify the path of the field map image files``

      #. ``Add more field maps?`` Loop back to 1

      #. ``Specify effective echo spacing for the functional data in
         seconds``

      #. ``Specify phase encoding direction for the functional data``

   -  ``No`` Skip this step

Features
========

Features are analyses that are carried out on the preprocessed data, in
other words, first-level analyses.

#. ``Specify first-level features?``

   -  ``Yes``

      #. ``Specify the feature type``

         -  ``Task-based``

            #. ``Specify feature name``
            #. ``Specify images to use``
            #. ``Specify the event file type``

            -  ``SPM multiple conditions`` A MATLAB .mat file containing
               three arrays: ``names`` (condition), ``onsets`` and
               ``durations``

            -  ``FSL 3-column`` One text file for each condition. Each
               file has its corresponding condition in the filename. The
               first column specifies the event onset, the second the
               duration. The third column of the files is ignored, so
               parametric modulation is not supported

            -  ``BIDS TSV`` A tab-separated table with named columns
               ``trial_type`` (condition), ``onset`` and ``duration``.
               While BIDS supports defining additional columns,
               ``HALFpipe`` will currently ignore these

            #. ``Specify the path of the event files``

            #. ``Select conditions to add to the model``

            #. ``Specify contrasts``

               #. ``Specify contrast name``

               #. ``Specify contrast values``

               #. ``Add another contrast?``

                  -  ``Yes`` Loop back to 1
                  -  ``No`` Continue

            #. ``Apply a temporal filter to the design matrix?`` A
               separate temporal filter can be specified for the design
               matrix. In contrast, the temporal filtering of the input
               image and any confound regressors added to the design
               matrix is specified in 10. In general, the two settings
               should match

            #. ``Apply smoothing?``

               -  ``Yes``

                  #. ``Specify smoothing FWHM in mm``

               -  ``No`` Continue

            #. ``Grand mean scaling will be applied with a mean of
               10000.000000``

            #. ``Temporal filtering will be applied using a
               gaussian-weighted filter`` ``Specify the filter width in
               seconds``

            #. ``Remove confounds?``

         -  ``Seed-based connectivity``

            #. ``Specify feature name``

            #. ``Specify images to use``

            #. ``Specify binary seed mask file(s)``

               #. ``Specify the path of the binary seed mask image
                  files``
               #. ``Check space values``
               #. ``Add binary seed mask image file``

         -  ``Dual regression``

            #. ``Specify feature name``
            #. ``Specify images to use``
            #. TODO

         -  ``Atlas-based connectivity matrix``

            #. ``Specify feature name``
            #. ``Specify images to use``
            #. TODO

         -  ``ReHo``

            #. ``Specify feature name``
            #. ``Specify images to use``
            #. TODO

         -  ``fALFF``

            #. ``Specify feature name``
            #. ``Specify images to use``
            #. TODO

   -  ``No`` Skip this step

#. ``Add another first-level feature?``

   -  ``Yes`` Loop back to 1
   -  ``No`` Continue

#. ``Output a preprocessed image?``

   -  ``Yes``

      #. ``Specify setting name``

      #. ``Specify images to use``

      #. ``Apply smoothing?``

         -  ``Yes``

            #. ``Specify smoothing FWHM in mm``

         -  ``No`` Continue

      #. ``Do grand mean scaling?``

         -  ``Yes``

            #. ``Specify grand mean``

         -  ``No`` Continue

      #. ``Apply a temporal filter?``

         -  ``Yes``

            #. ``Specify the type of temporal filter``

               -  ``Gaussian-weighted``
               -  ``Frequency-based``

         -  ``No`` Continue

      #. ``Remove confounds?``

   -  ``No`` Continue

Models
======

Models are statistical analyses that are carried out on the features.
Often these are known as second-level or group-level analyses.
There are currently two ways in which to run these analyses, either through
the user interface, or using a ‘group-level’ command directly in the terminal.
Shown first is the user interface method.

#. ``Specify group-level model?``

   -  ``Yes``

      #. ``Specify model type``

         -  ``Intercept-only`` This will apply an intercept-only model that captures a main effect of one or more of the first-level features.

            #. ``Specify model name``
            #. ``Aggregate scan-level statistics before analysis?`` This option may appear if there are multiple subject-level statistical images created, such as for multiple runs or sessions. If this option is selected (with an asterisk) then these features will be aggregated at the subject-level prior to group-level analysis. If the option is not selected, then group-level analyses will be performed separately for each listed first-level feature.
            #. ``Exclude subjects based on movement?``

               -  ``Yes``

                  #. ``Specify the maximum allowed mean framewise displacement in mm`` By selecting 0.5, this will exclude all subjects (or runs/sessions for a subject if ‘aggregation of scan-level statistics before analysis’ is not selected above) with a mean framewise displacement (root-mean-square) >0.5 mm. If aggregation of scan-level statistics before analysis is selected, the threshold will be applied to individual runs/sessions before the aggregate image is used in the group-level analyses. This may have important consequences if your require all runs to be present for a group-level analysis, for example if not all conditions are present in each run.
                  #. ``Specify the maximum allowed percentage of frames above the framewise
                     displacement threshold of (FD max from above)``

               -  ``No`` All subjects are retained for analyses regardless of movement.

         -  ``Linear model`` This will apply a linear model that captures main and/or interaction effects of one or more variables that must be present in a covariate/group data spreadsheet file. This file must contain a column with subject ID names identical to those used for the functional data.

            #. ``Specify model name``
            #. ``Aggregate scan-level statistics before analysis?`` See above
            #. ``Specify the path of the covariates/group data spreadsheet file`` Can be a .csv, .txt, .tsv, or .xlsx file

               #. ``Specify the column containing subject names``
               #. ``Specify the column data types`` Note that the black option is selected, the grey option is not. Toggle left/right keys to select or deselect options and up/down keys to move through the list of variables in your spreadsheet file.
               #. ``Specify the subjects to use`` Select the subjects to include in this analysis by their categorical variables. For multiple categorical variables, the intersection of the groups will be used.

            #. ``Exclude subjects based on movement?`` See above

               -  ``Yes``

                  #. ``Specify the maximum allowed mean framewise displacement in mm``
                  #. ``Specify the maximum allowed percentage of frames above the framewise
                     displacement threshold of (FD max from above)``

               -  ``No`` Continue

            #. ``Specify the variables to add to the model`` For all variables that are selected here, the model will output a main effect, controlling for all other variables selected by treating them as covariates of no interest. Anything not selected at this stage will be left entirely out of the model. All selected variables will be demeaned before being added to the model. Categorical variables are first dummy-coded, meaning  it is also possible to have string values for categorical variables.

               -  ``Listwise deletion`` Will remove subjects with a missing value from analysis entirely.
               -  ``Mean substitution`` For both continuous and categorical variables, will impute the average of all subjects with a valid observation for this variable. Since variables  are first demeaned, and categorical variables are dummy-coded, this means a value of '0' will be used for missing data in the group-level design matrix.

            #. ``Specify additional contrasts for categorical variables?`` For each variable, for the mean across all subjects, one contrast will be generated. This means that by default, there is only an omnibus F-test for categorical variables with more than two levels. If you would like to output additional contrasts between particular groups, this should be specified here.

               -  ``Yes``

                  #. ``Specify contrast name``
                  #. ``Specify the categorical variable for this contrast`` Toggle left/right to move through variables and press enter to select.
                  #. ``Specify contrast values``
                  #. ``Add another contrast?`` Loop back to a.

               -  ``No`` Continue

            #. ``Specify interaction terms?``

               -  ``Yes``

                  #. ``Specify the variables for which to calculate interaction terms``
                  #. ``Select which interaction terms to add to the model``

               -  ``No`` Continue

            #. ``Add another group-level model?``

               -  ``Yes`` Loop back to ``a. Specify model type``.
               -  ``No`` End of menu

			User interface will close and processing will begin


*************************************************
 Running on a high-performance computing cluster
*************************************************

#. Log in to your cluster’s head node

#. Request an interactive job. Refer to your cluster’s documentation for
   how to do this

#. |  In the interactive job, run the ``HALFpipe`` user interface, but
      add the flag ``--use-cluster`` to the end of the command.
   |  For example, ``singularity run --containall --bind /:/ext
      halfpipe-halfpipe-latest.sif --use-cluster``

#. As soon as you finish specifying all your data, features and models
   in the user interface, ``HALFpipe`` will now generate everything
   needed to run on the cluster. For hundreds of subjects, this can take
   up to a few hours.

#. When ``HALFpipe`` exits, edit the generated submit script
   ``submit.slurm.sh`` according to your cluster’s documentation and
   then run it. This submit script will calculate everything except
   group statistics.

#. As soon as all processing has been completed, you can run group
   statistics. This is usually very fast, so you can do this in an
   interactive session. Run ``singularity run --containall --bind /:/ext
   halfpipe-halfpipe-latest.sif --only-model-chunk`` and then select
   ``Run without modification`` in the user interface.

..

   A common issue with remote work via secure shell is that the
   connection may break after a few hours. For batch jobs this is not an
   issue, but for interactive jobs this can be quite frustrating. When
   the connection is lost, the node you were connected to will
   automatically quit all programs you were running. To prevent this,
   you can run interactive jobs within ``screen`` or ``tmux`` (whichever
   is available). These commands allow you to open sessions in the
   terminal that will continue running in the background even when you
   close or disconnect. Here’s a quick overview of how to use the
   commands (more in-depth documentation is available for example at
   http://www.dayid.org/comp/tm.html).

   #. Open a new screen/tmux session on the head node by running either
      ``screen`` or ``tmux``

   #. Request an interactive job from within the session, for example
      with ``srun --pty bash -i``

   #. Run the command that you want to run

   #. Detach from the screen/tmux session, meaning disconnecting with
      the ability to re-connect later For screen, this is done by first
      pressing ``Control+a``, then letting go, and then pressing ``d``
      on the keyboard. For tmux, it’s ``Control+b`` instead of
      ``Control+a``. Note that this is always ``Control``, even if
      you’re on a mac.

   #. Close your connection to the head node with ``Control+d``.
      ``screen``/``tmux`` will remain running in the background

   #. Later, connect again to the head node. Run ``screen -r`` or ``tmux
      attach`` to check back on the interactive job. If everything went
      well and the command you wanted to run finished, close the
      interactive job with ``Control+d`` and then the
      ``screen``/``tmux`` session with ``Control+d`` again. If the
      command hasn’t finished yet, detach as before and come back later

..

    Are you getting a "missing dependencies" error? Some clusters configure singularity with an option called `mount hostfs <https://sylabs.io/guides/3.9/user-guide/bind_paths_and_mounts.html#disabling-system-binds>`_ that will bind all cluster file systems into the container. These file systems may in some cases have paths that conflict with where software is installed in the ``HALFpipe`` container, effectively overwriting that software. You can disable this by adding the option ``--no-mount hostfs`` right after ``singularity run``.

****************
 Quality checks
****************

Please see the `manual <https://drive.google.com/file/d/1TMg9MRvBwZO8HB1UJmH0gm4tYaBVnvcQ/view>`_

*********
 Outputs
*********

   Outdated

-  A visual report page ``reports/index.html``

-  A table with image quality metrics ``reports/reportvals.txt``

-  A table containing the preprocessing status
   ``reports/reportpreproc.txt``

-  The untouched ``fmriprep`` derivatives. Some files have been omitted
   to save disk space ``fmriprep`` is very strict about only processing
   data that is compliant with the BIDS standard. As such, we may need
   to format subjects names for compliance. For example, an input
   subject named ``subject_01`` will appear as ``subject01`` in the
   ``fmriprep`` derivatives. ``derivatives/fmriprep``

Subject-level features
======================

-  |  For task-based, seed-based connectivity and dual regression
      features, ``HALFpipe`` outputs the statistical maps for the
      effect, the variance, the degrees of freedom of the variance and
      the z-statistic. In FSL, the effect and variance are also called
      ``cope`` and ``varcope``
   |  ``derivatives/halfpipe/sub-.../func/..._stat-effect_statmap.nii.gz``
   |  ``derivatives/halfpipe/sub-.../func/..._stat-variance_statmap.nii.gz``
   |  ``derivatives/halfpipe/sub-.../func/..._stat-dof_statmap.nii.gz``
   |  ``derivatives/halfpipe/sub-.../func/..._stat-z_statmap.nii.gz``
   |  The design and contrast matrix used for the final model will be
      outputted alongside the statistical maps
   |  ``derivatives/halfpipe/sub-.../func/sub-..._task-..._feature-..._desc-design_matrix.tsv``
   |  ``derivatives/halfpipe/sub-.../func/sub-..._task-..._feature-..._desc-contrast_matrix.tsv``

-  |  ReHo and fALFF are not calculated based on a linear model. As
      such, only one statistical map of the z-scaled values will be
      output
   |  ``derivatives/halfpipe/sub-.../func/..._alff.nii.gz``
   |  ``derivatives/halfpipe/sub-.../func/..._falff.nii.gz``
   |  ``derivatives/halfpipe/sub-.../func/..._reho.nii.gz``

-  For every feature, a ``.json`` file containing a summary of the
   preprocessing

-  |  settings, and a list of the raw data files that were used for the
      analysis (``RawSources``)
   |  ``derivatives/halfpipe/sub-.../func/....json``

-  |  For every feature, the corresponding brain mask is output beside
      the statistical maps. Masks do not differ between different
      features calculated, they are only copied out repeatedly for
      convenience
   |  ``derivatives/halfpipe/sub-.../func/...desc-brain_mask.nii.gz``

-  |  Atlas-based connectivity outputs the time series and the full
      covariance and correlation matrices as text files
   |  ``derivatives/halfpipe/sub-.../func/..._timeseries.txt``
   |  ``derivatives/halfpipe/sub-.../func/..._desc-covariance_matrix.txt``
   |  ``derivatives/halfpipe/sub-.../func/..._desc-correlation_matrix.txt``

Preprocessed images
===================

-  |  Masked, preprocessed BOLD image
   |  ``derivatives/halfpipe/sub-.../func/..._bold.nii.gz``

-  |  Just like for features
   |  ``derivatives/halfpipe/sub-.../func/..._bold.json``

-  |  Just like for features
   |  ``derivatives/halfpipe/sub-.../func/sub-..._task-..._setting-..._desc-brain_mask.nii.gz``

-  |  Filtered confounds time series, where all filters that are applied
      to the BOLD image are applied to the regressors as well. Note that
      this means that when grand mean scaling is active, confounds time
      series are also scaled, meaning that values such as ``framewise
      displacement`` can not be interpreted in terms of their original
      units anymore.
   |  ``derivatives/halfpipe/sub-.../func/sub-..._task-..._setting-..._desc-confounds_regressors.tsv``

Group-level
===========

-  |  For task-based group-level analyses, HALFpipe outputs the statistical maps for the effect, the variance, the degrees of freedom of the variance, and the t-statistic and z-statistic for each linear model that is specified, much as for the first-level features. These models are fit per session, task, first-level feature, first-level task contrast, and group-level contrast, where these exist.
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-effect_statmap.nii.gz``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-variance_statmap.nii.gz``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-dof_statmap.nii.gz``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-t_statmap.nii.gz``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-z_statmap.nii.gz``
   |
-  |  For every contrast, the mean and standard deviation of the regressor used in the analysis. Depending on brain coverage per subject, the model may include a different set of participants per voxel, meaning that the mean and standard deviation of a regressor may vary per voxel. This is why the output is a whole-brain image, not a single value for each statistic.
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_contrast-…_mean.nii.gz``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_contrast-…_std.nii.gz``
   |
-  |  For every contrast, the corresponding brain mask is output beside the statistical maps. Masks may differ between different features that are calculated, based on regressor inclusion criteria, sub-groups investigated, and missing data.
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_contrast-…_mask.nii.gz``
   |
-  |  For every model (even when a linear effect model has been specified), the intercept is output as one contrast, capturing the main effect of the first-level feature(s) investigated, treating all other group-level variables in that model as covariates of no interest.
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_contrast-Intercept…``
   |
-  |  For every contrast, a .json file containing a summary of the processing settings, a list of the raw data files that were used for the analysis, and important summary statistics. The "CriticalZ" value found here is calculated by FSL's ``smoothest`` using random field theory and corresponds to the z-score value at which you should threshold the group-level statistical map to achieve a family-wise-error-corrected alpha<0.05.
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/-…/…_task-…_feature-…_model-…_contrast-…_stat-effect_statmap.json``
   |
-  |  The design and contrast matrix used for the final model will be outputted alongside the statistical maps
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_desc-design_matrix.tsv``
   |  ``grouplevel/…/func/task-…feature-…taskcontrast-…/model-…/…_task-…_feature-…_model-…_desc-contrast_matrix.tsv``
   |


*****************
 Troubleshooting
*****************

-  If an error occurs, this will be output to the command line and
   simultaneously to the ``err.txt`` file in the working directory

-  If the error occurs while running, usually a text file detailing the
   error will be placed in the working directory. These are text files
   and their file names start with ``crash``

   -  Usually, the last line of these text files contains the error
      message. Please read this carefully, as may allow you to
      understand the error

   -  For example, consider the following error message: ``ValueError:
      shape (64, 64, 33) for image 1 not compatible with first image
      shape (64, 64, 34) with axis == None`` This error message may seem
      cryptic at first. However, looking at the message more closely, it
      suggests that two input images have different, incompatible
      dimensions. In this case, ``HALFpipe`` correctly recognized this
      issue, and there is no need for concern. The images in question
      will simply be excluded from preprocessing and/or analysis

   -  In some cases, the cause of the error can be a bug in the
      ``HALFpipe`` code. Please check that no similar issue has been
      reported `here on GitHub
      <https://github.com/HALFpipe/HALFpipe/issues>`__. In this case,
      please submit an `issue
      <https://github.com/HALFpipe/HALFpipe/issues/new/choose>`__.

********************
 Command line flags
********************

Control command line logging
============================

.. code:: bash

   --verbose

By default, only errors and warnings will be output to the command line.
This makes it easier to see when something goes wrong, because there is
less output. However, if you want to be able to inspect what is being
run, you can add the ``--verbose`` flag to the end of the command used
to call ``HALFpipe``.

Verbose logs are always written to the ``log.txt`` file in the working
directory, so going back and inspecting this log is always possible,
even if the ``--verbose`` flag was not specified.

Specifying the flag ``--debug`` will print additional, fine-grained
messages. It will also automatically start the `Python Debugger
<https://docs.python.org/3/library/pdb.html>`__ when an error occurs.
You should only use ``--debug`` if you know what you’re doing.

Automatically remove unneeded files
===================================

.. code:: bash

   --keep

``HALFpipe`` saves intermediate files for each pipeline step. This
speeds up re-running with different settings, or resuming after a job
after it was cancelled. The intermediate file are saved by the `nipype
<https://nipype.readthedocs.io/>`__ workflow engine, which is what
``HALFpipe`` uses internally. ``nipype`` saves the intermediate files in
the ``nipype`` folder in the working directory.

In environments with limited disk capacity, this can be problematic. To
limit disk usage, ``HALFpipe`` can delete intermediate files as soon as
they are not needed anymore. This behavior is controlled with the
``--keep`` flag.

The default option ``--keep some`` keeps all intermediate files from
fMRIPrep and MELODIC, which would take the longest to re-run. We believe
this is a good tradeoff between disk space and computer time. ``--keep
all`` turns of all deletion of intermediate files. ``--keep none``
deletes as much as possible, meaning that the smallest amount possible
of disk space will be used.

Configure nipype
================

.. code:: bash

   --nipype-<omp-nthreads|memory-gb|n-procs|run-plugin>

``HALFpipe`` chooses sensible defaults for all of these values.

Choose which parts to run or to skip
====================================

   Outdated

.. code:: bash

   --<only|skip>-<spec-ui|workflow|run|model-chunk>

A ``HALFpipe`` run is divided internally into three stages, spec-ui,
workflow, and run.

#. The ``spec-ui`` stage is where you specify things in the user
   interface. It creates the ``spec.json`` file that contains all the
   information needed to run ``HALFpipe``. To only run this stage, use
   the option ``--only-spec-ui``. To skip this stage, use the option
   ``--skip-spec-ui``

#. The ``workflow`` stage is where ``HALFpipe`` uses the ``spec.json``
   data to search for all the files that match what was input in the
   user interface. It then generates a ``nipype`` workflow for
   preprocessing, feature extraction and group models. ``nipype`` then
   validates the workflow and prepares it for execution. This usually
   takes a couple of minutes and cannot be parallelized. For hundreds of
   subjects, this may even take a few hours. This stage has the
   corresponding option ``--only-workflow`` and ``--skip-workflow``.

-  This stage saves several intermediate files. These are named
   ``workflow.{uuid}.pickle.xz``, ``execgraph.{uuid}.pickle.xz`` and
   ``execgraph.{n_chunks}_chunks.{uuid}.pickle.xz``. The ``uuid`` in the
   file name is a unique identifier generated from the ``spec.json``
   file and the input files. It is re-calculated every time we run this
   stage. The uuid algorithm produces a different output if there are
   any changes (such as when new input files for new subjects become
   available, or the ``spec.json`` is changed, for example to add a new
   feature or group model). Otherwise, the ``uuid`` stays the same.
   Therefore, if a workflow file with the calculated ``uuid`` already
   exists, then we do not need to run this stage. We can simple reuse
   the workflow from the existing file, and save some time.

-  In this stage, we can also decide to split the execution into chunks.
   The flag ``--subject-chunks`` creates one chunk per subject. The flag
   ``--use-cluster`` automatically activates ``--subject-chunks``. The
   flag ``--n-chunks`` allows the user to specify a specific number of
   chunks. This is useful if the execution should be spread over a set
   number of computers. In addition to these, a model chunk is
   generated.

#. The ``run`` stage loads the
   ``execgraph.{n_chunks}_chunks.{uuid}.pickle.xz`` file generated in
   the previous step and runs it. This file usually contains two chunks,
   one for the subject level preprocessing and feature extraction
   (“subject level chunk”), and one for group statistics (“model
   chunk”). To run a specific chunk, you can use the flags
   ``--only-chunk-index ...`` and ``--only-model-chunk``.

Working directory
=================

.. code:: bash

   --workdir

..

   TODO

Data file system root
=====================

.. code:: bash

   --fs-root

The ``HALFpipe`` container, or really most containers, contain the
entire base system needed to run

*********
 Contact
*********

For questions or support, please submit an `issue
<https://github.com/HALFpipe/HALFpipe/issues/new/choose>`__ or contact
us via e-mail at enigma@charite.de.
