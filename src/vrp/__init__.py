"""VRP / OR-Tools optimization domain."""

__all__ = ["run_optimization_task"]


def __getattr__(name: str):
    if name == "run_optimization_task":
        from src.vrp.controller import run_optimization_task

        return run_optimization_task
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
