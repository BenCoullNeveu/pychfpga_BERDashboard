# syntax=docker/dockerfile:1

## NOTE: Environemt Parameter DOCKER_BUILDKIT=1 is required to be set, before the build,
## docker build -f Dockerfile -t chimefrb/pychfpga:latest --ssh github_ssh_key=$SSH_AUTH_SOCK .
## docker build -f Dockerfile -t chimefrb/pychfpga:latest --ssh github_ssh_key=/path/to/id_rsa .
## where $SSH_AUTH_SOCK contains the path of the unix file socket for the ssh-agent

########################################################
# Base Image with Linux Dependencies
########################################################
FROM python:3.7-slim as base

# Install Linux Dependencies
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends curl openssh-client git git-lfs \

# Add github.com to known_hosts
RUN set -ex \
    && mkdir -p -m 0600 ~/.ssh \
    && ssh-keyscan github.com >> ~/.ssh/known_hosts \
    && ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

########################################################
# Python Dependencies Layer
########################################################
FROM base as runtime
# Copy project dependencies into the docker image.
COPY . /pychfpga

# Change directory to /pychfpga
WORKDIR /pychfpga

# Install project dependencies.
RUN --mount=type=ssh,id=github_ssh_key set -ex \
    && pip install --upgrade pip \
    && pip install -e .

# Exposing ports normally used by the application
EXPOSE 54321-54330

# Default entrypoint
CMD ["fpga_master", "--help"]