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

"""FlagSpec and MatcherSpec Protocol definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FlagSpec(Protocol):
    """Specification for a command-line flag/parameter."""

    def get_name(self) -> str:
        """Return the flag name."""
        ...

    def get_desc(self) -> str:
        """Return the flag description."""
        ...

    def is_required(self) -> bool:
        """Return whether this flag is required."""
        ...

    def no_args(self) -> bool:
        """Return whether this flag takes no arguments (boolean flag)."""
        ...


@runtime_checkable
class MatcherSpec(FlagSpec, Protocol):
    """Matcher specification, extends FlagSpec for ModelSpec matcher definitions."""

    pass
