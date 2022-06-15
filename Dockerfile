# syntax=docker/dockerfile:1

## NOTE: Environemt Parameter   is required to be set, before the build,

# SSH key to bitbucket must be available from ssh-agent
# export BUILDKIT_PROGRESS=plain # optional, for more verbose output
# export DOCKER_BUILDKIT=1
# docker build --target deploy -t pychfpga:jfc_dev --ssh default .


## docker build -t pychfpga:jfc_dev --ssh ssh_key=$SSH_AUTH_SOCK .
## docker build -f Dockerfile -t chimefrb/pychfpga:latest --ssh ssh_key=/path/to/id_rsa .
## where $SSH_AUTH_SOCK contains the path of the unix file socket for the ssh-agent

# Based on recommendations at
#   https://testdriven.io/blog/docker-best-practices/
#
########################################################
# Base Image with Linux Dependencies
########################################################
FROM python:3.8-slim as base

# Install Linux Dependencies
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends \
        # curl \
        # Include openssh for ssh-keyscan
        openssh-client \
        git \
        git-lfs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # make sure git LFS is initialized
    && git lfs install \
    # Add public keys from remote git repos to our known host list so we don't have complaints when pip installs depencies from our private repos
    && mkdir -p -m 0600 ~/.ssh \
    # && ssh-keyscan github.com >> ~/.ssh/known_hosts \
    && ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

########################################################
# Python Dependencies
########################################################
FROM base as pychfpga_install

RUN pip install --upgrade pip
RUN pip install wheel

#    && git clone git@bitbucket.org:winterlandcosmology/pychfpga.git --depth 1 --branch jfc/dev --single-branch /pychfpga \
#    && git clone git@bitbucket.org:chime/ch_config.git --depth 1 --branch jfc/dev --single-branch /ch_config

# Change directory to /pychfpga
WORKDIR /pychfpga

# Setup the virtual environment
# We install the python packages in there so all the install products are in a single place so we can copy them in the final image
ENV VIRTUAL_ENV=/pychfpga/.venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Pre-install requirements since these change very rarely
COPY requirements.txt .
RUN --mount=type=ssh \
    set -ex \
    && pip install -r requirements.txt


# Install pychfpga repo. This step is re-done every time any of the files in the repo changes
# pip still checks all of the dependencies (which means accessing the repo for private packages),
# but then all those should already have been cached in the previous image stage
COPY . .
RUN --mount=type=ssh set -ex \
    && pip install .


########################################################
# Deployment image
########################################################

FROM python:3.8-slim as deploy
WORKDIR /pychfpga

# Setup the path to point to the virtual environment that we will copy in the next step
ENV VIRTUAL_ENV=/pychfpga/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Exposing ports normally used by the application
EXPOSE 54321-54330

COPY --from=pychfpga_install $VIRTUAL_ENV $VIRTUAL_ENV

# Default entrypoint
CMD ["echo", "Please specify pychfpga command: fpga_master <config_file>:<item>, raw_acq, ps <config_file>:<item>, gps <config_file>:<item>"]

# FROM runtime as production
# RUN set -ex \
#     && rm -rf /pychfpga/docs \
#     && rm -rf /pychfpga/pychfpga/arm_firmware \
#     && rm -rf /pychfpga/.git

# FROM runtime as developer
# RUN set -ex \
#     && pip install ipython