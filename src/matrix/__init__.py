"""Distance / duration matrix domain."""

__all__ = ["DistanceMatrixManager"]


def __getattr__(name: str):
    if name == "DistanceMatrixManager":
        from src.matrix.manager import DistanceMatrixManager

        return DistanceMatrixManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
