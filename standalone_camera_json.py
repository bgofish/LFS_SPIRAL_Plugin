"""
standalone_camera_json.py
Pure-Python camera animation generator.
Produces Lichtfeld-compatible JSON from circular or spiral paths.
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


# ── Look-at quaternion ────────────────────────────────────────────────────────

def _normalize(v: tuple) -> tuple:
    x, y, z = v
    n = math.sqrt(x*x + y*y + z*z)
    if n < 1e-10:
        return (0.0, 0.0, 1.0)
    return (x/n, y/n, z/n)


def _look_at_quaternion(position: tuple, target: tuple) -> list[float]:
    """
    Return a quaternion [qw, qx, qy, qz] that rotates the camera to look
    from *position* toward *target*.

    Convention: Y-up world, +Z camera forward (SuperSplat / Lichtfeld).
    """
    fx, fy, fz = _normalize((
        target[0] - position[0],
        target[1] - position[1],
        target[2] - position[2],
    ))

    # Choose world-up; fall back to -Z if forward is nearly vertical
    if abs(fy) > 0.99:
        world_up = (0.0, 0.0, -1.0 if fy > 0 else 1.0)
    else:
        world_up = (0.0, 1.0, 0.0)

    # Right = world_up x forward
    rx = world_up[1]*fz - world_up[2]*fy
    ry = world_up[2]*fx - world_up[0]*fz
    rz = world_up[0]*fy - world_up[1]*fx
    right = _normalize((rx, ry, rz))

    # Up = forward x right  (re-orthogonalised)
    ux = fy*right[2] - fz*right[1]
    uy = fz*right[0] - fx*right[2]
    uz = fx*right[1] - fy*right[0]

    # Rotation matrix columns: right | up | forward  (+Z forward convention)
    m00, m10, m20 = right
    m01, m11, m21 = ux, uy, uz
    m02, m12, m22 = fx, fy, fz

    # Matrix → quaternion (qw, qx, qy, qz)
    trace = m00 + m11 + m22
    if trace > 0:
        s  = 0.5 / math.sqrt(trace + 1.0)
        qw = 0.25 / s
        qx = (m21 - m12) * s
        qy = (m02 - m20) * s
        qz = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s  = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s  = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s  = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s

    n = math.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
    if n > 1e-12:
        qw /= n; qx /= n; qy /= n; qz /= n

    return [qw, qx, qy, qz]


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
        duration = frames / fps

        # Direction: clockwise = negative angle progression
        dir_sign = -1.0 if direction == "clockwise" else 1.0

        keyframes = []
        base_indices = list(range(0, frames, max(1, keyframe_step)))

        # When keyframe_step > 1, inject index 1 and frames-2 for smoother ends
        extra = set()
        if keyframe_step > 1:
            if 1 not in base_indices and 1 < frames:
                extra.add(1)
            if (frames - 2) not in base_indices and (frames - 2) >= 0:
                extra.add(frames - 2)

        frame_indices = sorted(set(base_indices) | extra)

        for i in frame_indices:
            t_norm = i / max(frames - 1, 1)   # 0 … 1

            if animation_type == "circular":
                angle  = dir_sign * 2.0 * math.pi * t_norm
                cam_x  = cx + radius * math.sin(angle)
                cam_y  = cy
                cam_z  = cz + radius * math.cos(angle)
                look_target = list(center) if target is None else list(target)

            else:  # spiral
                angle  = dir_sign * 2.0 * math.pi * spiral_loops * t_norm
                r      = start_radius + (end_radius - start_radius) * t_norm
                h      = start_height + (end_height - start_height) * t_norm
                cam_x  = cx + r * math.sin(angle)
                cam_y  = cy + h
                cam_z  = cz + r * math.cos(angle)

                if spiral_follow_y:
                    look_target = [cx, cam_y + spiral_y_offset, cz]
                elif target is not None:
                    look_target = list(target)
                else:
                    look_target = list(center)

            # Auto-target: place look point at target_distance along the
            # direction toward the nominal look_target
            if target_distance is not None:
                dx = look_target[0] - cam_x
                dy = look_target[1] - cam_y
                dz = look_target[2] - cam_z
                d  = math.sqrt(dx*dx + dy*dy + dz*dz)
                if d > 1e-12:
                    look_target = [
                        cam_x + dx/d * target_distance,
                        cam_y + dy/d * target_distance,
                        cam_z + dz/d * target_distance,
                    ]

            position = [cam_x, cam_y, cam_z]

            # Optional Z-up → Y-up coordinate conversion
            if convert_coords:
                position    = [position[0],    position[2],    -position[1]]
                look_target = [look_target[0], look_target[2], -look_target[1]]

            qw, qx, qy, qz = _look_at_quaternion(position, look_target)

            # Lichtfeld +Y_up convention: negate Y on position and reflect
            # the rotation across the XZ plane (negate qx and qz) so the
            # camera still points at the correct target with correct up.
            position[1] = -position[1]
            qx = -qx
            qz = -qz

            time_s = round(i / fps, precision)

            def r(v):
                return round(v, precision)

            keyframes.append({
                "easing":          0,
                "focal_length_mm": r(focal_length),
                "time":            time_s,
                "position":        [r(position[0]), r(position[1]), r(position[2])],
                "rotation":        [r(qw), r(qx), r(qy), r(qz)],
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
