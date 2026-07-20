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

"""PredicateResult - validation result container."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PredicateResult:
    """Result of a predicate validation check."""

    success: bool
    error: str = ""

    @classmethod
    def ok(cls) -> PredicateResult:
        """Create a successful result."""
        return cls(success=True)

    @classmethod
    def fail(cls, msg: str) -> PredicateResult:
        """Create a failed result with error message."""
        return cls(success=False, error=msg)
