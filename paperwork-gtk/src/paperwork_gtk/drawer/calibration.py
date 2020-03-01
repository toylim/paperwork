"""
Ensure calibration is displayed when a scan is running.
"""

import logging

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Drawer(object):
    def __init__(self, core, drawing_area):
        self.core = core
        self.drawing_area = drawing_area
        self.content_full_size = None
        self.scan_id = None
        self.active = False
        self.drawer = None

    def _get_frame(self):
        return self.core.call_success("config_get", "scanner_calibration")

    def _set_frame(self, frame):
        self.core.call_all("config_put", "scanner_calibration", frame)

    def set_content_full_size(self, size):
        if self.active:
            self.stop()

        self.content_full_size = size
        self.core.call_all(
            "config_add_observer", "scanner_calibration",
            self.request_redraw
        )
        self.drawer = self.core.call_success(
            "draw_frame_start", self.drawing_area, self.content_full_size,
            self._get_frame, self._set_frame
        )
        self.active = True

    def request_redraw(self, *args, **kwargs):
        if self.drawer is None:
            return
        self.drawer.request_redraw()

    def stop(self):
        self.core.call_all("draw_frame_stop", self.drawing_area)
        self.core.call_all(
            "config_remove_observer", "scanner_calibration",
            self.request_redraw
        )
        self.active = False


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.drawers = {}  # drawing_area --> drawer

    def get_interfaces(self):
        return [
            'gtk_drawer_calibration',
            'gtk_drawer_scan',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_drawer_frame',
                'defaults': ['paperwork_gtk.drawer.frame'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': 'scanner_calibration',
                'defaults': [
                    'paperwork_backend.guesswork.cropping.calibration'
                ]
            },
        ]

    def draw_calibration_start(self, drawing_area, content_full_size):
        drawer = Drawer(self.core, drawing_area)
        drawer.set_content_full_size(content_full_size)
        self.drawers[drawing_area] = drawer

    def draw_calibration_stop(self, drawing_area):
        if drawing_area not in self.drawers:
            return
        self.drawers.pop(drawing_area).stop()

    def draw_scan_start(self, drawing_area, scan_id=None):
        if drawing_area in self.drawers:
            drawer = self.drawers[drawing_area]
        else:
            drawer = Drawer(self.core, drawing_area)
        drawer.scan_id = scan_id
        self.drawers[drawing_area] = drawer

    def draw_scan_stop(self, drawing_area):
        if drawing_area not in self.drawers:
            return
        self.drawers.pop(drawing_area).stop()

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        for drawer in self.drawers.values():
            if drawer.scan_id is None or scan_id == drawer.scan_id:
                drawer.set_content_full_size(
                    (scan_params.get_width(), scan_params.get_height())
                )
