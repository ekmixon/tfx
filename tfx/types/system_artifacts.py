# Copyright 2021 Google LLC. All Rights Reserved.
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
"""A set of System Artifact types.

It matches the MLMD system artifacts types from:
third_party/ml_metadata/metadata_store/mlmd_types.py
"""

from tfx.types.artifact import Artifact

from ml_metadata.metadata_store import mlmd_types


class Dataset(Artifact):
  TYPE_NAME = mlmd_types.Dataset().name


class Model(Artifact):
  TYPE_NAME = mlmd_types.Model().name


class Statistics(Artifact):
  TYPE_NAME = mlmd_types.Statistics().name


class Metrics(Artifact):
  TYPE_NAME = mlmd_types.Metrics().name
