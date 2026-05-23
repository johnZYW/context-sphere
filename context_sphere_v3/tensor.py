"""Tiny tensor-like container for dependency-free early slices.

Slice 1 needs deterministic shapes and values, but not tensor math. PyTorch
becomes required when the triangular folding implementation starts.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from operator import mul


@dataclass(frozen=True)
class SimpleTensor:
    shape: tuple[int, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        expected = reduce(mul, self.shape, 1)
        if expected != len(self.values):
            raise ValueError(f"shape {self.shape} expects {expected} values, observed {len(self.values)}")

    @classmethod
    def from_flat(cls, shape: tuple[int, ...], values: list[float] | tuple[float, ...]) -> "SimpleTensor":
        return cls(shape=shape, values=tuple(float(value) for value in values))

    @classmethod
    def zeros(cls, shape: tuple[int, ...]) -> "SimpleTensor":
        return cls(shape=shape, values=(0.0,) * reduce(mul, shape, 1))

    def to_json_summary(self) -> dict[str, object]:
        return {
            "shape": list(self.shape),
            "value_count": len(self.values),
            "preview": list(self.values[:8]),
        }
