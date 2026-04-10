# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: GPL-3.0-or-later

import lichtfeld as lf
from .camera_gen_panel import CameraGenPanel

_classes = [CameraGenPanel]


def on_load():
    for cls in _classes:
        lf.register_class(cls)
    lf.log.info("camera_json_gen loaded")


def on_unload():
    for cls in reversed(_classes):
        lf.unregister_class(cls)
    lf.log.info("camera_json_gen unloaded")
