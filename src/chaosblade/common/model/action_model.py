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

"""ActionModel - represents an action with its flags/parameters."""

from __future__ import annotations


class ActionModel:
    """Model representing a chaos action and its parameters."""

    __slots__ = ("_name", "_flags")

    def __init__(self, name: str) -> None:
        self._name = name
        self._flags: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Return the action name."""
        return self._name

    def get_flag(self, key: str) -> str | None:
        """Get a flag value by key."""
        return self._flags.get(key)

    def add_flag(self, key: str, value: str) -> None:
        """Add or update a flag."""
        self._flags[key] = value

    @property
    def flags(self) -> dict[str, str]:
        """Return a copy of all flags."""
        return self._flags.copy()

    def __repr__(self) -> str:
        return f"ActionModel(name={self._name!r}, flags={self._flags})"
