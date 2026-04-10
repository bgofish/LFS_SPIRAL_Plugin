# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: GPL-3.0-or-later

"""JSON Camera Generator Panel for Lichtfeld Studio."""

from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import lichtfeld as lf

from standalone_camera_json import StandaloneCameraGenerator, focal_length_to_fov


# ── File dialog helper ────────────────────────────────────────────────────────

def _browse_json_save(title: str, default_path: str) -> str | None:
    """Open a Save-As dialog filtered to .json via PowerShell SaveFileDialog."""
    try:
        if sys.platform == "win32":
            initial_dir = default_path if os.path.isdir(default_path) else os.path.expanduser("~")
            initial_dir = initial_dir.replace(chr(92), chr(92) + chr(92))
            ps_script = f"""
                Add-Type -AssemblyName System.Windows.Forms
                $dialog = New-Object System.Windows.Forms.SaveFileDialog
                $dialog.Title = "{title}"
                $dialog.InitialDirectory = "{initial_dir}"
                $dialog.Filter = "Camera JSON (*.json)|*.json|All Files (*.*)|*.*"
                $dialog.FilterIndex = 1
                $dialog.DefaultExt = "json"
                if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                    Write-Output $dialog.FileName
                }}
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            path = result.stdout.strip()
            return path if path else None
    except Exception as exc:
        lf.log.error(f"CameraGen: file dialog error – {exc}")
    return None


# ── Panel ─────────────────────────────────────────────────────────────────────

class CameraGenPanel(lf.ui.Panel):
    id                 = "camera_json_gen.panel"
    label              = "Camera JSON"
    space              = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order              = 400
    template           = str(Path(__file__).resolve().with_name("camera_gen_panel.rml"))
    height_mode        = lf.ui.PanelHeightMode.CONTENT
    update_interval_ms = 500

    # ── Defaults ──────────────────────────────────────────────────────────────

    def __init__(self):
        self._handle = None

        # Animation type / direction
        self._anim_type  = "circular"   # "circular" | "spiral"
        self._direction  = "clockwise"  # "clockwise" | "counterclockwise"

        # Circular
        self._radius = 10.0

        # Spiral
        self._spiral_loops    = 2.0
        self._start_radius    = 5.0
        self._end_radius      = 15.0
        self._start_height    = 0.0
        self._end_height      = 10.0
        self._spiral_follow_y = False
        self._spiral_y_offset = 0.0

        # Center
        self._center_x = 0.0
        self._center_y = 0.0
        self._center_z = 0.0

        # Target
        self._use_auto_target   = False
        self._target_distance   = 10.0
        self._target_x          = 0.0
        self._target_y          = 0.0
        self._target_z          = 0.0

        # Animation settings
        self._frames       = 180
        self._fps          = 24
        self._focal_length = 35.0
        self._sensor_size  = 32.0

        # Export options
        self._precision       = 6
        self._keyframe_step   = 1
        self._convert_coords  = False

        # Output
        self._output_path = ""

        # Status
        self._status              = ""
        self._status_class        = "text-default"
        self._generating          = False
        self._pending_output_path = None   # written by browse thread, applied in on_update

        self._load_settings()

    @classmethod
    def poll(cls, context) -> bool:
        return True

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_bind_model(self, ctx):
        model = ctx.create_data_model("camera_gen_panel")

        # Animation type
        model.bind("anim_circular",
                   lambda: self._anim_type == "circular",
                   lambda v: self._set_anim_type("circular", v))
        model.bind("anim_spiral",
                   lambda: self._anim_type == "spiral",
                   lambda v: self._set_anim_type("spiral", v))

        # Direction
        model.bind("dir_clockwise",
                   lambda: self._direction == "clockwise",
                   lambda v: self._set_direction("clockwise", v))
        model.bind("dir_ccw",
                   lambda: self._direction == "counterclockwise",
                   lambda v: self._set_direction("counterclockwise", v))

        # Visibility guards for conditional sections
        model.bind_func("is_circular", lambda: self._anim_type == "circular")
        model.bind_func("is_spiral",   lambda: self._anim_type == "spiral")
        model.bind_func("is_manual_target", lambda: not self._use_auto_target)
        model.bind_func("is_auto_target",   lambda: self._use_auto_target)

        # Circular params
        model.bind("radius_str",
                   lambda: f"{self._radius:.2f}",
                   lambda v: self._set_float("_radius", v, 0.01, 10000.0))

        # Spiral params
        model.bind("spiral_loops_str",
                   lambda: f"{self._spiral_loops:.1f}",
                   lambda v: self._set_float("_spiral_loops", v, 0.1, 100.0))
        model.bind("start_radius_str",
                   lambda: f"{self._start_radius:.2f}",
                   lambda v: self._set_float("_start_radius", v, 0.01, 10000.0))
        model.bind("end_radius_str",
                   lambda: f"{self._end_radius:.2f}",
                   lambda v: self._set_float("_end_radius", v, 0.01, 10000.0))
        model.bind("start_height_str",
                   lambda: f"{self._start_height:.2f}",
                   lambda v: self._set_float("_start_height", v, -10000.0, 10000.0))
        model.bind("end_height_str",
                   lambda: f"{self._end_height:.2f}",
                   lambda v: self._set_float("_end_height", v, -10000.0, 10000.0))
        model.bind("spiral_follow_y",
                   lambda: self._spiral_follow_y,
                   lambda v: self._set_bool("_spiral_follow_y", v))
        model.bind("spiral_y_offset_str",
                   lambda: f"{self._spiral_y_offset:.2f}",
                   lambda v: self._set_float("_spiral_y_offset", v, -1000.0, 1000.0))

        # Center coords
        model.bind("center_x_str",
                   lambda: f"{self._center_x:.3f}",
                   lambda v: self._set_float("_center_x", v, -1e6, 1e6))
        model.bind("center_y_str",
                   lambda: f"{self._center_y:.3f}",
                   lambda v: self._set_float("_center_y", v, -1e6, 1e6))
        model.bind("center_z_str",
                   lambda: f"{self._center_z:.3f}",
                   lambda v: self._set_float("_center_z", v, -1e6, 1e6))

        # Target mode
        model.bind("use_auto_target",
                   lambda: self._use_auto_target,
                   lambda v: self._set_bool("_use_auto_target", v))
        model.bind("target_distance_str",
                   lambda: f"{self._target_distance:.2f}",
                   lambda v: self._set_float("_target_distance", v, 0.01, 1e6))
        model.bind("target_x_str",
                   lambda: f"{self._target_x:.3f}",
                   lambda v: self._set_float("_target_x", v, -1e6, 1e6))
        model.bind("target_y_str",
                   lambda: f"{self._target_y:.3f}",
                   lambda v: self._set_float("_target_y", v, -1e6, 1e6))
        model.bind("target_z_str",
                   lambda: f"{self._target_z:.3f}",
                   lambda v: self._set_float("_target_z", v, -1e6, 1e6))

        # Animation settings
        model.bind("frames_str",
                   lambda: str(self._frames),
                   lambda v: self._set_int("_frames", v, 1, 100000))
        model.bind("fps_str",
                   lambda: str(self._fps),
                   lambda v: self._set_int("_fps", v, 1, 240))
        model.bind("focal_length_str",
                   lambda: f"{self._focal_length:.1f}",
                   lambda v: self._set_float("_focal_length", v, 1.0, 2000.0))
        model.bind("sensor_size_str",
                   lambda: f"{self._sensor_size:.1f}",
                   lambda v: self._set_float("_sensor_size", v, 1.0, 200.0))

        # Export options
        model.bind("precision_str",
                   lambda: str(self._precision),
                   lambda v: self._set_int("_precision", v, 1, 10))
        model.bind("keyframe_step_str",
                   lambda: str(self._keyframe_step),
                   lambda v: self._set_int("_keyframe_step", v, 1, 1000))
        model.bind("convert_coords",
                   lambda: self._convert_coords,
                   lambda v: self._set_bool("_convert_coords", v))

        # Derived display
        model.bind_func("fov_str",      self._get_fov_str)
        model.bind_func("duration_str", self._get_duration_str)

        # Output path
        model.bind("output_path",
                   lambda: self._output_path,
                   lambda v: (setattr(self, "_output_path", str(v)), self._save_settings()))

        # Status
        model.bind_func("status_text",  lambda: self._status)
        model.bind_func("status_class", lambda: self._status_class)

        # Events
        model.bind_event("do_generate",              self._on_generate)
        model.bind_event("do_browse",                self._on_browse)
        model.bind_event("do_send_to_sequencer",     self._on_send_to_sequencer)
        model.bind_event("preset_close_orbit",       self._preset_close_orbit)
        model.bind_event("preset_medium_orbit",   self._preset_medium_orbit)
        model.bind_event("preset_wide_orbit",     self._preset_wide_orbit)
        model.bind_event("preset_rising_spiral",  self._preset_rising_spiral)
        model.bind_event("preset_desc_spiral",    self._preset_desc_spiral)

        self._handle = model.get_handle()

    def on_update(self, doc):
        if self._pending_output_path is not None:
            self._output_path         = self._pending_output_path
            self._pending_output_path = None
            self._save_settings()
            self._dirty("output_path")

    def on_unmount(self, doc):
        doc.remove_data_model("camera_gen_panel")
        self._handle = None

    # ── Derived display helpers ───────────────────────────────────────────────

    def _get_fov_str(self) -> str:
        try:
            fov = focal_length_to_fov(self._focal_length, self._sensor_size)
            return f"{fov:.1f}°"
        except Exception:
            return "—"

    def _get_duration_str(self) -> str:
        try:
            secs = self._frames / self._fps
            return f"{secs:.2f}s"
        except Exception:
            return "—"

    # ── Setters ───────────────────────────────────────────────────────────────

    def _set_anim_type(self, value: str, flag):
        """Only act when the radio that was just turned ON fires."""
        flag_bool = flag if isinstance(flag, bool) else str(flag).lower() not in ("false", "0", "")
        if flag_bool:
            self._anim_type = value
            self._save_settings()
            self._dirty("is_circular", "is_spiral", "anim_circular", "anim_spiral")

    def _set_direction(self, value: str, flag):
        flag_bool = flag if isinstance(flag, bool) else str(flag).lower() not in ("false", "0", "")
        if flag_bool:
            self._direction = value
            self._save_settings()
            self._dirty("dir_clockwise", "dir_ccw")

    def _set_float(self, attr: str, value, lo: float, hi: float):
        try:
            v = max(lo, min(hi, float(value)))
        except (TypeError, ValueError):
            return
        setattr(self, attr, v)
        self._save_settings()
        self._dirty("fov_str", "duration_str")

    def _set_int(self, attr: str, value, lo: int, hi: int):
        try:
            v = max(lo, min(hi, int(value)))
        except (TypeError, ValueError):
            return
        setattr(self, attr, v)
        self._save_settings()
        self._dirty("fov_str", "duration_str")

    def _set_bool(self, attr: str, value):
        if isinstance(value, str):
            v = value.lower() not in ("false", "0", "")
        else:
            v = bool(value)
        setattr(self, attr, v)
        self._save_settings()
        self._dirty("is_manual_target", "is_auto_target")

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_send_to_sequencer(self, handle, event, args):
        if not self._output_path.strip():
            self._set_status("Generate and save a JSON file first.", error=True)
            return
        if not Path(self._output_path).exists():
            self._set_status("File not found — generate it first.", error=True)
            return
        try:
            from training_render.core.state import State
            from training_render.core.lfs_path_player import LFSPathPlayer
            State.track3_path    = self._output_path
            State._track3_player = LFSPathPlayer(self._output_path)
            State.track3_loaded  = True
            State.active_track   = "track3"
            lf.log.info(f"CameraGen: loaded path into sequencer from {self._output_path!r}")
            self._set_status("✓ Loaded into path sequencer (Track 3).")
        except Exception as e:
            lf.log.error(f"CameraGen: send to sequencer failed – {e}")
            self._set_status(f"Load failed: {e}", error=True)

    def _on_browse(self, handle, event, args):
        initial = (Path(self._output_path).parent.as_posix()
                   if self._output_path else os.path.expanduser("~"))
        def _browse():
            picked = _browse_json_save("Save camera JSON", initial)
            if picked:
                self._pending_output_path = picked
        threading.Thread(target=_browse, daemon=True).start()

    def _on_generate(self, handle, event, args):
        if self._generating:
            return
        if not self._output_path.strip():
            self._set_status("Set an output path first.", error=True)
            return
        self._generating = True
        self._set_status("Generating…")
        thread = threading.Thread(target=self._generate_thread, daemon=True)
        thread.start()

    def _generate_thread(self):
        try:
            gen = StandaloneCameraGenerator()

            center = (self._center_x, self._center_y, self._center_z)
            target = None if self._use_auto_target else (
                self._target_x, self._target_y, self._target_z)
            target_distance = self._target_distance if self._use_auto_target else None

            data = gen.generate_camera_animation(
                animation_type  = self._anim_type,
                direction       = self._direction,
                center          = center,
                target          = target,
                target_distance = target_distance,
                radius          = self._radius,
                start_radius    = self._start_radius,
                end_radius      = self._end_radius,
                start_height    = self._start_height,
                end_height      = self._end_height,
                spiral_loops    = self._spiral_loops,
                frames          = self._frames,
                fps             = self._fps,
                focal_length    = self._focal_length,
                sensor_size     = self._sensor_size,
                convert_coords  = self._convert_coords,
                precision       = self._precision,
                keyframe_step   = self._keyframe_step,
                spiral_follow_y = self._spiral_follow_y,
                spiral_y_offset = self._spiral_y_offset,
            )
            gen.save_json(data, self._output_path)
            kf_count = len(data["keyframes"])
            self._set_status(
                f"✓ Saved {kf_count} keyframes → {Path(self._output_path).name}"
            )
        except Exception as e:
            lf.log.error(f"CameraGen error: {e}")
            self._set_status(f"Error: {e}", error=True)
        finally:
            self._generating = False

    # ── Presets ───────────────────────────────────────────────────────────────

    def _preset_close_orbit(self, handle, event, args):
        self._anim_type = "circular"
        self._radius    = 3.0
        self._center_x = 0.0; self._center_y = -3.0; self._center_z = 0.0
        self._target_x = 0.0; self._target_y =  0.0; self._target_z = 0.0
        self._frames = 120; self._fps = 24; self._direction = "clockwise"
        self._use_auto_target = False
        self._auto_output("close_orbit_camera.json")
        self._save_settings(); self._dirty_all()

    def _preset_medium_orbit(self, handle, event, args):
        self._anim_type = "circular"
        self._radius    = 10.0
        self._center_x = 0.0; self._center_y = -10.0; self._center_z = 0.0
        self._target_x = 0.0; self._target_y =   0.0; self._target_z = 0.0
        self._frames = 180; self._fps = 24; self._direction = "clockwise"
        self._use_auto_target = False
        self._auto_output("medium_orbit_camera.json")
        self._save_settings(); self._dirty_all()

    def _preset_wide_orbit(self, handle, event, args):
        self._anim_type = "circular"
        self._radius    = 20.0
        self._center_x = 0.0; self._center_y = -20.0; self._center_z = 0.0
        self._target_x = 0.0; self._target_y =   0.0; self._target_z = 0.0
        self._frames = 240; self._fps = 24; self._direction = "clockwise"
        self._use_auto_target = False
        self._auto_output("wide_orbit_camera.json")
        self._save_settings(); self._dirty_all()

    def _preset_rising_spiral(self, handle, event, args):
        self._anim_type     = "spiral"
        self._spiral_loops  = 2.0
        self._start_radius  = 5.0;  self._end_radius = 5.0
        self._start_height  = 0.0;  self._end_height = -10.0
        self._center_x = 0.0; self._center_y = 0.0; self._center_z = 5.0
        self._target_x = 0.0; self._target_y = 0.0; self._target_z = 5.0
        self._frames = 240; self._fps = 24; self._direction = "counterclockwise"
        self._spiral_follow_y = False
        self._use_auto_target = False
        self._auto_output("rising_spiral_camera.json")
        self._save_settings(); self._dirty_all()

    def _preset_desc_spiral(self, handle, event, args):
        self._anim_type     = "spiral"
        self._spiral_loops  = 3.0
        self._start_radius  = 20.0; self._end_radius = 5.0
        self._start_height  = 15.0; self._end_height = 0.0
        self._center_x = 0.0; self._center_y = 0.0; self._center_z = 7.5
        self._target_x = 0.0; self._target_y = 0.0; self._target_z = 7.5
        self._frames = 300; self._fps = 24; self._direction = "clockwise"
        self._spiral_follow_y = False
        self._use_auto_target = False
        self._auto_output("descending_spiral_camera.json")
        self._save_settings(); self._dirty_all()

    def _auto_output(self, filename: str):
        if not self._output_path:
            import os
            self._output_path = str(Path(os.getcwd()) / filename)

    # ── Settings persistence ──────────────────────────────────────────────────

    @staticmethod
    def _settings_path() -> Path:
        return Path(__file__).resolve().with_name("settings.json")

    def _load_settings(self):
        try:
            data = json.loads(self._settings_path().read_text(encoding="utf-8"))
            d = data.get("params", {})
            for attr, key, cast in [
                ("_anim_type",       "anim_type",       str),
                ("_direction",       "direction",       str),
                ("_radius",          "radius",          float),
                ("_spiral_loops",    "spiral_loops",    float),
                ("_start_radius",    "start_radius",    float),
                ("_end_radius",      "end_radius",      float),
                ("_start_height",    "start_height",    float),
                ("_end_height",      "end_height",      float),
                ("_spiral_follow_y", "spiral_follow_y", bool),
                ("_spiral_y_offset", "spiral_y_offset", float),
                ("_center_x",        "center_x",        float),
                ("_center_y",        "center_y",        float),
                ("_center_z",        "center_z",        float),
                ("_use_auto_target", "use_auto_target", bool),
                ("_target_distance", "target_distance", float),
                ("_target_x",        "target_x",        float),
                ("_target_y",        "target_y",        float),
                ("_target_z",        "target_z",        float),
                ("_frames",          "frames",          int),
                ("_fps",             "fps",             int),
                ("_focal_length",    "focal_length",    float),
                ("_sensor_size",     "sensor_size",     float),
                ("_precision",       "precision",       int),
                ("_keyframe_step",   "keyframe_step",   int),
                ("_convert_coords",  "convert_coords",  bool),
                ("_output_path",     "output_path",     str),
            ]:
                if key in d:
                    raw = d[key]
                    if cast is bool:
                        setattr(self, attr, raw if isinstance(raw, bool) else bool(raw))
                    else:
                        setattr(self, attr, cast(raw))
        except FileNotFoundError:
            pass
        except Exception as e:
            lf.log.error(f"CameraGen settings load error: {e}")

    def _save_settings(self):
        try:
            path = self._settings_path()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            data["params"] = {
                "anim_type":       self._anim_type,
                "direction":       self._direction,
                "radius":          self._radius,
                "spiral_loops":    self._spiral_loops,
                "start_radius":    self._start_radius,
                "end_radius":      self._end_radius,
                "start_height":    self._start_height,
                "end_height":      self._end_height,
                "spiral_follow_y": self._spiral_follow_y,
                "spiral_y_offset": self._spiral_y_offset,
                "center_x":        self._center_x,
                "center_y":        self._center_y,
                "center_z":        self._center_z,
                "use_auto_target": self._use_auto_target,
                "target_distance": self._target_distance,
                "target_x":        self._target_x,
                "target_y":        self._target_y,
                "target_z":        self._target_z,
                "frames":          self._frames,
                "fps":             self._fps,
                "focal_length":    self._focal_length,
                "sensor_size":     self._sensor_size,
                "precision":       self._precision,
                "keyframe_step":   self._keyframe_step,
                "convert_coords":  self._convert_coords,
                "output_path":     self._output_path,
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            lf.log.error(f"CameraGen settings save error: {e}")

    # ── Dirty helpers ─────────────────────────────────────────────────────────

    def _dirty(self, *fields):
        if self._handle:
            for f in fields:
                self._handle.dirty(f)

    def _dirty_all(self):
        self._dirty(
            "anim_circular", "anim_spiral", "is_circular", "is_spiral",
            "dir_clockwise", "dir_ccw",
            "radius_str",
            "spiral_loops_str", "start_radius_str", "end_radius_str",
            "start_height_str", "end_height_str",
            "spiral_follow_y", "spiral_y_offset_str",
            "center_x_str", "center_y_str", "center_z_str",
            "use_auto_target", "is_manual_target", "is_auto_target",
            "target_distance_str", "target_x_str", "target_y_str", "target_z_str",
            "frames_str", "fps_str", "focal_length_str", "sensor_size_str",
            "precision_str", "keyframe_step_str", "convert_coords",
            "fov_str", "duration_str",
            "output_path",
            "status_text", "status_class",
        )

    def _set_status(self, msg: str, error: bool = False):
        self._status       = msg
        self._status_class = "text-muted" if error else "text-accent"
        self._dirty("status_text", "status_class")
