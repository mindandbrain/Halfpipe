# syntax=docker/dockerfile:1.10

ARG fmriprep_version=24.1.0

FROM condaforge/miniforge3 AS conda
RUN conda config --system --append channels https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public \
    && conda config --system --set remote_max_retries 10 \
    --set remote_backoff_factor 2 \
    --set remote_connect_timeout_secs 60 \
    --set remote_read_timeout_secs 240

# Build all custom recipes in one command. We build our own conda packages to simplify
# the environment creation process, as some of them are not available on conda-forge
FROM conda AS builder
RUN conda install --yes "conda-build"

RUN cat <<EOF > "/usr/bin/retry"
#!/bin/bash
set -euo pipefail
timeout="1"
attempt="1"
until "\$@"; do
    if [ "\${attempt}" -ge "5" ]; then
        exit "$?"
    fi
    sleep "\${timeout}"
    timeout=\$((timeout * 10))
    attempt=\$((attempt + 1))
done
EOF
RUN chmod "+x" "/usr/bin/retry"

# We manually specify the numpy version for all conda build commands to silence
# an irrelevant warning as per https://github.com/conda/conda-build/issues/3170

## SAME RECIPES, SAME VERSION ##

FROM builder AS rmath
RUN --mount=source=recipes/rmath,target=/rmath \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "rmath"

FROM builder AS pytest-textual-snapshot
RUN --mount=source=recipes/pytest-textual-snapshot,target=/pytest-textual-snapshot \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "pytest-textual-snapshot"

FROM builder AS nipype
RUN --mount=source=recipes/traits,target=/traits \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "traits"
RUN --mount=source=recipes/nipype,target=/nipype \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "nipype"
RUN --mount=source=recipes/niflow-nipype1-workflows,target=/niflow-nipype1-workflows \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "niflow-nipype1-workflows"

## EXCLUSIVE FROM FMRIPREP 24 ##

FROM builder AS afni
RUN --mount=source=recipes/24.1.0/afni,target=/afni \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "afni"

FROM builder AS acres
RUN --mount=source=recipes/24.1.0/acres,target=/acres \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "acres"

FROM builder AS mapca
RUN --mount=source=recipes/24.1.0/mapca,target=/mapca \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "mapca"

FROM builder AS migas
RUN --mount=source=recipes/24.1.0/migas,target=/migas \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "migas"

## SAME RECIPES, DIFFERENT VERSION ##

FROM builder AS nitransforms
ARG fmriprep_version
RUN --mount=source=recipes/${fmriprep_version}/nitransforms,target=/nitransforms \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "nitransforms"

FROM builder AS tedana
ARG fmriprep_version
COPY --from=mapca /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/tedana,target=/tedana \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "tedana"

FROM builder AS templateflow
ARG fmriprep_version
RUN --mount=source=recipes/20.2.7/templateflow,target=/templateflow \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "templateflow"

#Exclusive from 24.1.0
FROM builder AS nireports
ARG fmriprep_version
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
# needs templateflow, but we can use conda version. The templateflow we build is only necessary
# for fmriprep 20
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/24.1.0/nireports,target=/nireports \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "nireports"

FROM builder AS niworkflows
ARG fmriprep_version
COPY --from=nitransforms /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=templateflow /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=acres /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/niworkflows,target=/niworkflows \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "niworkflows"

FROM builder AS sdcflows
ARG fmriprep_version
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=niworkflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=templateflow /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=migas /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/sdcflows,target=/sdcflows \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "sdcflows"

FROM builder AS smriprep
ARG fmriprep_version
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=niworkflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=templateflow /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=migas /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/smriprep,target=/smriprep \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "smriprep"

FROM builder AS fmriprep
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=niworkflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=sdcflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=smriprep /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=tedana /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=nireports /opt/conda/conda-bld /opt/conda/conda-bld
ARG fmriprep_version
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/fmriprep,target=/fmriprep \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "fmriprep"

#Exclusive from 24.0.1
FROM builder AS fmripost_aroma
ARG fmriprep_version
COPY --from=nipype /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=niworkflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=nitransforms /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=sdcflows /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=smriprep /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=nireports /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=fmriprep /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
RUN --mount=source=recipes/${fmriprep_version}/fmripost_aroma,target=/fmripost_aroma \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "fmripost_aroma"

FROM builder AS halfpipe
ARG fmriprep_version
COPY --from=fmriprep /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=rmath /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=pytest-textual-snapshot /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=afni /opt/conda/conda-bld /opt/conda/conda-bld
COPY --from=fmripost_aroma /opt/conda/conda-bld /opt/conda/conda-bld
RUN conda index /opt/conda/conda-bld
# Mount .git folder too for setuptools_scm
RUN --mount=source=recipes/${fmriprep_version}/halfpipe,target=/halfpipe/recipes/${fmriprep_version}/halfpipe \
    --mount=source=src,target=/halfpipe/src \
    --mount=source=pyproject.toml,target=/halfpipe/pyproject.toml \
    --mount=source=.git,target=/halfpipe/.git \
    --mount=type=cache,target=/opt/conda/pkgs \
    retry conda build --no-anaconda-upload --numpy "1.24" "halfpipe/recipes/${fmriprep_version}/halfpipe"

# We install built recipes and clean unnecessary files such as static libraries
FROM conda AS install

RUN conda config --system --append channels https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public
COPY --from=halfpipe /opt/conda/conda-bld/ /opt/conda/conda-bld/
RUN --mount=type=cache,target=/opt/conda/pkgs \
    conda install --yes --use-local \
    "python=3.11" "libzlib=1.2.13" "nodejs" "sqlite" "halfpipe" "mamba=1.3.1"

RUN conda clean --yes --all --force-pkgs-dirs \
    && find /opt/conda -follow -type f -name "*.a" -delete \
    && rm -rf /opt/conda/conda-bld

# Re-apply `matplotlib` settings after re-installing conda. This silences
# a warning that will otherwise be printed every time `matplotlib` is imported.
# This command re-caches fonts and sets 'Agg' as default backend for `matplotlib`.
# Taken from fmriprep's Dockerfile
RUN python -c "from matplotlib import font_manager" && \
    sed -i '/backend:/s/^#*//;/^backend/s/: .*/: Agg/' \
    $( python -c "import matplotlib; print(matplotlib.matplotlib_fname())" )

# Create the final image based on existing fmriprep image
FROM nipreps/fmriprep:${fmriprep_version}

# Create these empty directories, so that they can be used for singularity
# bind mounts later
RUN mkdir /ext /host \
    && chmod a+rwx /ext /host

# Use `/var/cache` for downloaded resources instead of `/home/fmriprep/.cache`,
# because it is less likely to be obscured by default bind mounts when running with
# singularity. These have been reported by users running on specific HPC systems
ENV XDG_CACHE_HOME="/var/cache" \
    HALFPIPE_RESOURCE_DIR="/var/cache/halfpipe" \
    TEMPLATEFLOW_HOME="/var/cache/templateflow"
RUN mv /home/fmriprep/.cache/templateflow /var/cache

# We install ants previously using conda (through a dependency in the halfpipe
# recipe), to get an important bug fix (#691). We delete the ants that came with
# fmriprep and update the `PATH` to reflect the new ants location
RUN rm -rf /usr/lib/ants
ENV PATH="${PATH//\/usr\/lib\/ants/}"

# Add `coinstac` server components
COPY --from=coinstacteam/coinstac-base:latest /server/ /server/

# Add git config for datalad commands
RUN git config --global user.name "HALFpipe" \
    && git config --global user.email "halfpipe@fmri.science"

# Copy `conda` from `install` stage
RUN rm -rf /opt/conda
COPY --from=install /opt/conda/ /opt/conda/

# The `fmriprep` container comes with conda in `/usr/local/miniconda`.
# Instead, halfpipe uses conda from the corresponding docker image,
# where it is installed in `/opt/conda`.
# Therefore, we update the `PATH` to reflect new conda location
ENV PATH="${PATH/\/usr\/local\/miniconda\/bin//opt/conda/bin}"

# We set up our own FSLDIR variable. We used to inherit it from fmriprep in version 20,
# but in 24.0.1 they placed it at /opt/conda/envs/fmriprep and we want to get rid
# of that location to prevent conflicts between our environment and fmriprep's one
ENV LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1 \
    FSLDIR="/opt/conda/" \
    # options:
    # /opt/conda/share/fsl
    # /opt/conda/bin/fsl
    # /opt/conda/bin
    # /opt/conda/
    FSLOUTPUTTYPE="NIFTI_GZ" \
    FSLMULTIFILEQUIT="TRUE" \
    FSLLOCKDIR="" \
    FSLMACHINELIST="" \
    FSLREMOTECALL="" \
    FSLGECUDAQ="cuda.q" \
    FSLWISH="/opt/conda/bin/fslwish"
# point to FSLwish, but maybe not necessary since we dont want graphics

RUN ln -s /opt/conda/bin/fslversion /opt/conda/etc/fslversion && \
    echo "6.0.4" > /opt/conda/bin/fslversion

ENV PATH="$FSLDIR/bin:$PATH"
RUN /bin/bash -c "source /opt/conda/bin/activate base && conda list"

# Download all resources
RUN --mount=source=src/halfpipe/resource.py,target=/resource.py \
    python /resource.py

ENTRYPOINT ["/opt/conda/bin/halfpipe"]
