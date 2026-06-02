"""Surface edit operations (brushes) for the editable terrain layer.

These are pure, deterministic functions that mutate a height field (metres) given
the world-space coordinates of each sample. Determinism + world-space evaluation
is what keeps edits seamless across tile boundaries: the same brush evaluated at
the same world coordinate yields the same result regardless of which tile owns
that sample.

Designed surface-first but extensible: each op is a small declarative record, so
a future volumetric layer can add new op types without changing the transport.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np

# Registered surface op types.
OP_RAISE_LOWER = "raise_lower"
OP_FLATTEN = "flatten"
OP_SMOOTH = "smooth"
SURFACE_OPS = {OP_RAISE_LOWER, OP_FLATTEN, OP_SMOOTH}

FALLOFF_SMOOTH = "smooth"
FALLOFF_LINEAR = "linear"
FALLOFF_CONSTANT = "constant"


@dataclass
class EditOp:
    """A single brush stroke, expressed in Unreal world centimetres so the UE
    client can send exactly what it has. The service converts to projected
    metres for evaluation.
    """

    type: str
    center_x_cm: float
    center_y_cm: float
    radius_m: float
    strength_m: float = 0.0          # raise_lower: +up / -down (metres)
    target_height_m: float = 0.0     # flatten target (metres)
    falloff: str = FALLOFF_SMOOTH
    iterations: int = 1              # smooth passes
    op_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        from .limits import MAX_EDIT_RADIUS_M, MAX_EDIT_ITERATIONS
        if self.type not in SURFACE_OPS:
            raise ValueError(f"Unknown edit op type: {self.type}")
        if not (0.0 < self.radius_m <= MAX_EDIT_RADIUS_M):
            raise ValueError(
                f"radius_m must be in (0, {MAX_EDIT_RADIUS_M}], got {self.radius_m}"
            )
        if self.falloff not in (FALLOFF_SMOOTH, FALLOFF_LINEAR, FALLOFF_CONSTANT):
            raise ValueError(f"Unknown falloff: {self.falloff}")
        if not (1 <= self.iterations <= MAX_EDIT_ITERATIONS):
            raise ValueError(
                f"iterations must be in [1, {MAX_EDIT_ITERATIONS}], got {self.iterations}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EditOp":
        fields = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in fields})


def _falloff_weights(dist: np.ndarray, radius_m: float, falloff: str) -> np.ndarray:
    """Brush weight in [0,1]: 1 at centre, 0 at/beyond the radius."""
    t = np.clip(dist / radius_m, 0.0, 1.0)
    if falloff == FALLOFF_CONSTANT:
        w = np.where(t < 1.0, 1.0, 0.0)
    elif falloff == FALLOFF_LINEAR:
        w = 1.0 - t
    else:  # smooth (smoothstep-like bell)
        w = (1.0 - t * t) ** 2
    return np.where(dist <= radius_m, w, 0.0)


def apply_op(heights_m: np.ndarray, easting: np.ndarray, northing: np.ndarray,
             op: EditOp, center_e: float, center_n: float) -> np.ndarray:
    """Apply ``op`` to a height field in place-returning fashion.

    Args:
        heights_m: (H, W) current heights (metres). Not mutated.
        easting, northing: (H, W) projected coords of each sample (metres).
        op: the edit.
        center_e, center_n: brush centre in projected metres.

    Returns:
        New (H, W) height field with the edit applied.
    """
    dist = np.hypot(easting - center_e, northing - center_n)
    w = _falloff_weights(dist, op.radius_m, op.falloff)
    out = heights_m.astype(np.float64, copy=True)

    if op.type == OP_RAISE_LOWER:
        out += op.strength_m * w

    elif op.type == OP_FLATTEN:
        out += w * (op.target_height_m - out)

    elif op.type == OP_SMOOTH:
        for _ in range(max(1, op.iterations)):
            blurred = _box_blur(out)
            out = out + w * (blurred - out)

    return out


def _box_blur(a: np.ndarray) -> np.ndarray:
    """3x3 mean blur with edge replication (cheap smoothing kernel)."""
    p = np.pad(a, 1, mode="edge")
    acc = (
        p[0:-2, 0:-2] + p[0:-2, 1:-1] + p[0:-2, 2:]
        + p[1:-1, 0:-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
        + p[2:, 0:-2] + p[2:, 1:-1] + p[2:, 2:]
    )
    return acc / 9.0
