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

"""Built-in fault injection executors.

Provides the three core chaos actions:
- delay: inject latency into method calls
- exception: throw exceptions from method calls
- return: tamper with method return values

Plus DirectlyInjection executors for:
- cpu: CPU burn
- memory: memory fill
- process: process kill
"""

from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor

__all__ = [
    "DelayActionExecutor",
    "ThrowExceptionExecutor",
    "ReturnValueExecutor",
]
