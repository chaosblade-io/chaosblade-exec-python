# Copyright 2025 The ChaosBlade Authors
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

"""Request - HTTP request parameter container."""

from __future__ import annotations


class Request:
    """Container for HTTP request parameters."""

    __slots__ = ("_params",)

    def __init__(self, params: dict[str, str] | None = None) -> None:
        self._params: dict[str, str] = params or {}

    def get_param(self, key: str) -> str | None:
        """Get a parameter value by key."""
        return self._params.get(key)

    @property
    def params(self) -> dict[str, str]:
        """Return all parameters."""
        return self._params

    def __repr__(self) -> str:
        return f"Request(params={self._params})"
