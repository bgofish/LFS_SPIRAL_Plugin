"""
standalone_camera_json.py
Pure-Python camera animation generator.
Produces SuperSplat-compatible JSON from circular or spiral paths.
No Blender, no tkinter required.
"""

from __future__ import annotations
import json
import math
from pathlib import Path


# ── FOV helper ────────────────────────────────────────────────────────────────

def focal_length_to_fov(focal_length_mm: float, sensor_width_mm: float) -> float:
    """Convert focal length + sensor width to horizontal FOV in degrees."""
    return math.degrees(2.0 * math.atan(sensor_width_mm / (2.0 * focal_length_mm)))


# ── Look-at matrix ────────────────────────────────────────────────────────────

def _look_at(eye: tuple, target: tuple) -> list[float]:
    """
    Return a 4x4 column-major look-at matrix (list of 16 floats) that places
    a camera at *eye* pointing toward *target*.  Y-up world convention.
    """
    ex, ey, ez = eye
    tx, ty, tz = target

    fwd = _normalize((tx - ex, ty - ey, tz - ez))
    # Degenerate guard: if forward is nearly straight up, tilt the up hint
    up_hint = (0.0, 1.0, 0.0)
    if abs(_dot(fwd, up_hint)) > 0.999:
        up_hint = (0.0, 0.0, 1.0)

    right = _normalize(_cross(up_hint, fwd))
    up    = _cross(fwd, right)

    # Column-major: [right | up | fwd | translation]
    # Lichtfeld camera convention: +Z forward, so col2 = +fwd (not -fwd)
    return [
         right[0],  right[1],  right[2], 0.0,
            up[0],     up[1],     up[2], 0.0,
          fwd[0],    fwd[1],    fwd[2],  0.0,
            ex,        ey,        ez,    1.0,
    ]


def _normalize(v: tuple) -> tuple:
    x, y, z = v
    n = math.sqrt(x*x + y*y + z*z)
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    return (x/n, y/n, z/n)


def _cross(a: tuple, b: tuple) -> tuple:
    ax, ay, az = a
    bx, by, bz = b
    return (ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx)


def _dot(a: tuple, b: tuple) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _mat4_to_rotation_translation(m: list[float]) -> tuple[list[float], list[float]]:
    """
    Decompose a column-major 4×4 matrix into
    rotation (as [qx, qy, qz, qw]) and translation [tx, ty, tz].
    """
    # Extract rotation 3×3 (column-major: m[0..2] = col0, m[4..6] = col1, m[8..10] = col2)
    r00, r10, r20 = m[0], m[1], m[2]
    r01, r11, r21 = m[4], m[5], m[6]
    r02, r12, r22 = m[8], m[9], m[10]
    tx, ty, tz    = m[12], m[13], m[14]

    trace = r00 + r11 + r22
    if trace > 0:
        s  = 0.5 / math.sqrt(trace + 1.0)
        qw = 0.25 / s
        qx = (r21 - r12) * s
        qy = (r02 - r20) * s
        qz = (r10 - r01) * s
    elif r00 > r11 and r00 > r22:
        s  = 2.0 * math.sqrt(1.0 + r00 - r11 - r22)
        qw = (r21 - r12) / s
        qx = 0.25 * s
        qy = (r01 + r10) / s
        qz = (r02 + r20) / s
    elif r11 > r22:
        s  = 2.0 * math.sqrt(1.0 + r11 - r00 - r22)
        qw = (r02 - r20) / s
        qx = (r01 + r10) / s
        qy = 0.25 * s
        qz = (r12 + r21) / s
    else:
        s  = 2.0 * math.sqrt(1.0 + r22 - r00 - r11)
        qw = (r10 - r01) / s
        qx = (r02 + r20) / s
        qy = (r12 + r21) / s
        qz = 0.25 * s

    # Normalise quaternion
    qn = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if qn > 1e-12:
        qx /= qn; qy /= qn; qz /= qn; qw /= qn

    return [qx, qy, qz, qw], [tx, ty, tz]


# ── Generator ─────────────────────────────────────────────────────────────────

class StandaloneCameraGenerator:
    """Generate SuperSplat camera-path JSON without any external dependencies."""

    def generate_camera_animation(
        self,
        animation_type:  str   = "circular",
        direction:       str   = "clockwise",
        center:          tuple = (0.0, 0.0, 0.0),
        target:          tuple | None = None,
        target_distance: float | None = None,
        # Circular
        radius:          float = 10.0,
        # Spiral
        start_radius:    float = 5.0,
        end_radius:      float = 15.0,
        start_height:    float = 0.0,
        end_height:      float = 10.0,
        spiral_loops:    float = 2.0,
        # Common
        frames:          int   = 180,
        fps:             int   = 24,
        focal_length:    float = 35.0,
        sensor_size:     float = 32.0,
        convert_coords:  bool  = False,
        precision:       int   = 6,
        keyframe_step:   int   = 1,
        spiral_follow_y: bool  = False,
        spiral_y_offset: float = 0.0,
    ) -> dict:
        cx, cy, cz = center
        fov = focal_length_to_fov(focal_length, sensor_size)
        duration = frames / fps

        # Direction multiplier: clockwise = negative angle progression in standard math
        dir_sign = -1.0 if direction == "clockwise" else 1.0

        keyframes = []
        frame_indices = range(0, frames, max(1, keyframe_step))

        for i in frame_indices:
            t_norm = i / max(frames - 1, 1)   # 0 … 1
            angle  = dir_sign * 2.0 * math.pi * t_norm

            if animation_type == "circular":
                cam_x = cx + radius * math.cos(angle)
                cam_y = cy
                cam_z = cz + radius * math.sin(angle)
                look_target = (cx, cy, cz) if target is None else target

            else:  # spiral
                angle *= spiral_loops
                r   = start_radius + (end_radius - start_radius) * t_norm
                h   = start_height + (end_height - start_height) * t_norm
                cam_x = cx + r * math.cos(angle)
                cam_y = cy + h
                cam_z = cz + r * math.sin(angle)

                if spiral_follow_y:
                    look_target = (cx, cam_y + spiral_y_offset, cz)
                elif target is not None:
                    look_target = target
                else:
                    look_target = (cx, cy, cz)

            # Auto-target override
            if target_distance is not None:
                fwd = _normalize((look_target[0] - cam_x,
                                   look_target[1] - cam_y,
                                   look_target[2] - cam_z))
                look_target = (cam_x + fwd[0] * target_distance,
                                cam_y + fwd[1] * target_distance,
                                cam_z + fwd[2] * target_distance)

            eye = (cam_x, cam_y, cam_z)

            if convert_coords:
                # Z-up → Y-up: swap Y and Z, negate new Z
                eye         = (eye[0], eye[2], -eye[1])
                look_target = (look_target[0], look_target[2], -look_target[1])

            mat      = _look_at(eye, look_target)
            rotation, _ = _mat4_to_rotation_translation(mat)
            translation  = list(eye)   # world-space position passed through directly

            time_s = round(i / fps, precision)

            def r(v):
                return round(v, precision)

            keyframes.append({
                "easing":          0,
                "focal_length_mm": r(focal_length),
                "time":            time_s,
                "position":        [r(translation[0]), r(translation[1]), r(translation[2])],
                "rotation":        [r(rotation[0]),    r(rotation[1]),    r(rotation[2]),    r(rotation[3])],
            })

        return {
            "version": 1,
            "type": "camera_animation",
            "duration": round(duration, precision),
            "fps": fps,
            "frames": frames,
            "animation_type": animation_type,
            "direction": direction,
            "keyframes": keyframes,
        }

    def save_json(self, data: dict, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
