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

"""ChaosBlade chaos experiment executor for Python applications.

Public API:
    ChaosBladeAgent - Main entry point for starting/stopping the agent
    Model           - Experiment model (target + action + matchers)
    EnhancerModel   - Runtime model built by enhancers
    Injector        - Core injection engine
"""

__version__ = "1.8.0"

# Lazy imports to avoid circular dependencies


def __getattr__(name: str):
    """Lazy-load public API symbols on first access."""
    if name == "ChaosBladeAgent":
        from chaosblade.bootstrap.agent import ChaosBladeAgent
        return ChaosBladeAgent
    elif name == "Model":
        from chaosblade.common.model.model import Model
        return Model
    elif name == "EnhancerModel":
        from chaosblade.common.model.enhancer_model import EnhancerModel
        return EnhancerModel
    elif name == "Injector":
        from chaosblade.common.injection.injector import Injector
        return Injector
    raise AttributeError(f"module 'chaosblade' has no attribute {name!r}")


__all__ = [
    "__version__",
    "ChaosBladeAgent",
    "Model",
    "EnhancerModel",
    "Injector",
]
