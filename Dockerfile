# syntax=docker/dockerfile:1

## NOTE: Environemt Parameter DOCKER_BUILDKIT=1 is required to be set, before the build,
## docker build -f Dockerfile -t chimefrb/pychfpga:latest --ssh github_ssh_key=$SSH_AUTH_SOCK .
## docker build -f Dockerfile -t chimefrb/pychfpga:latest --ssh github_ssh_key=/path/to/id_rsa .
## where $SSH_AUTH_SOCK contains the path of the unix file socket for the ssh-agent

########################################################
# Base Image with Linux Dependencies
########################################################
FROM python:3.8-slim as base

# Install Linux Dependencies
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends curl openssh-client git git-lfs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p -m 0600 ~/.ssh \
    && ssh-keyscan github.com >> ~/.ssh/known_hosts \
    && ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

########################################################
# Python Dependencies Layer
########################################################
FROM base as runtime

RUN --mount=type=ssh,id=github_ssh_key set -ex \
    && git lfs install \
    && pip install --upgrade pip \
    && git clone git@bitbucket.org:winterlandcosmology/pychfpga.git --depth 1 --branch jfc/dev --single-branch /pychfpga \
    && git clone git@bitbucket.org:winterlandcosmology/ch_config.git --depth 1 --branch jfc/dev --single-branch /ch_config \
    && rm -rf /pychfpga/docs \
    && rm -rf /pychfpga/pychfpga/arm_firmware \
    && rm -rf /pychfpga/.git

# Change directory to /pychfpga
WORKDIR /pychfpga

# Install project dependencies.
RUN --mount=type=ssh,id=github_ssh_key set -ex \
    && pip install -e .

# Exposing ports normally used by the application
EXPOSE 54321-54330

# Default entrypoint
CMD ["fpga_master", "--help"]