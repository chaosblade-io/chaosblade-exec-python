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
