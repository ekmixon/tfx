# Copyright 2020 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module for LocalDockerModelServerRunner."""

import os
import time
from typing import Any, Dict

from absl import logging
import docker
from docker import errors as docker_errors
from tfx.components.infra_validator import error_types
from tfx.components.infra_validator import serving_bins
from tfx.components.infra_validator.model_server_runners import base_runner
from tfx.proto import infra_validator_pb2

_POLLING_INTERVAL_SEC = 1


def _make_docker_client(config: infra_validator_pb2.LocalDockerConfig):
  params = {}
  if config.client_timeout_seconds:
    params['timeout'] = config.client_timeout_seconds
  if config.client_base_url:
    params['base_url'] = config.client_base_url
  if config.client_api_version:
    params['version'] = config.client_api_version
  return docker.DockerClient(**params)


def _find_host_port(ports: Dict[str, Any], container_port: int) -> str:
  """Find host port from container port mappings.

  `ports` is a nested dictionary of the following structure:

  {'8500/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32769'}],
   '8501/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32768'}]}

  Args:
    ports: Dictionary of docker container port mapping.
    container_port: Corresponding container port you're looking for.

  Returns:
    A found host port.

  Raises:
    ValueError: No corresponding host port was found.
  """
  if mappings := ports.get(f'{container_port}/tcp'):
    return mappings[0].get('HostPort')
  else:
    raise ValueError(
        f'No HostPort found for ContainerPort={container_port} (all port mappings: {ports})'
    )


class LocalDockerRunner(base_runner.BaseModelServerRunner):
  """A model server runner that runs in a local docker runtime.

  You need to pre-install docker in the machine that is running InfraValidator
  component. For that reason, it is recommended to use this runner only for
  testing purpose.
  """

  def __init__(self, model_path: str,
               serving_binary: serving_bins.ServingBinary,
               serving_spec: infra_validator_pb2.ServingSpec):
    """Make a local docker runner.

    Args:
      model_path: An IV-flavored model path. (See model_path_utils.py)
      serving_binary: A ServingBinary to run.
      serving_spec: A ServingSpec instance.
    """
    self._model_path = model_path
    self._serving_binary = serving_binary
    self._serving_spec = serving_spec
    self._docker = _make_docker_client(serving_spec.local_docker)
    self._container = None
    self._endpoint = None

  def __repr__(self):
    return 'LocalDockerRunner(image: {image})'.format(
        image=self._serving_binary.image)

  def GetEndpoint(self):
    assert self._endpoint is not None, (
        'Endpoint is not yet created. You should call Start() first.')
    return self._endpoint

  def Start(self):
    assert self._container is None, (
        'You cannot start model server multiple times.')

    if not isinstance(self._serving_binary, serving_bins.TensorFlowServing):
      raise NotImplementedError(
          f'Unsupported serving binary {type(self._serving_binary).__name__}')

    is_local = os.path.isdir(self._model_path)
    run_params = self._serving_binary.MakeDockerRunParams(
        model_path=self._model_path,
        needs_mount=is_local)
    logging.info('Running container with parameter %s', run_params)
    self._container = self._docker.containers.run(**run_params)

  def WaitUntilRunning(self, deadline):
    assert self._container is not None, 'container has not been started.'

    while time.time() < deadline:
      try:
        # Reload container attributes from server. This is the only right way to
        # retrieve the latest container status from docker engine.
        self._container.reload()
        status = self._container.status
      except docker_errors.NotFound:
        # If the job has been aborted and container has specified auto_removal
        # to True, we might get a NotFound error during container.reload().
        raise error_types.JobAborted(
            'Container not found. Possibly removed after the job has been '
            'aborted.')
      # The container is just created and not yet in the running status.
      if status == 'created':
        time.sleep(_POLLING_INTERVAL_SEC)
        continue
      # The container is running :)
      if status == 'running':
        host_port = _find_host_port(self._container.ports,
                                    self._serving_binary.container_port)
        self._endpoint = f'localhost:{host_port}'
        return
      # Docker status is one of {'created', 'restarting', 'running', 'removing',
      # 'paused', 'exited', or 'dead'}. Status other than 'created' and
      # 'running' indicates the job has been aborted.
      raise error_types.JobAborted(
          f'Job has been aborted (container status={status})')

    raise error_types.DeadlineExceeded(
        'Deadline exceeded while waiting for the container to be running.')

  def Stop(self):
    if self._container:
      logging.info('Stopping container.')
      self._container.stop()
    self._docker.close()
