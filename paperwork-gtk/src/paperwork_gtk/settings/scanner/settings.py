import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -400

    def __init__(self):
        super().__init__()
        self.config = [
            (
                'scanner_dev_id', 'scanner_device_value',
                _("No scanner selected"), "{}".format
            ),
            (
                'scanner_resolution', 'scanner_resolution_value',
                _("No resolution selected"), _("{} dpi").format
            ),
            (
                'scanner_mode', 'scanner_mode_value',
                _("No mode selected"), self._translate_mode
            ),
        ]

    def get_interfaces(self):
        return [
            'gtk_settings_scanner',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings.scanner",
            "settings.glade"
        )

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree,
            _("Scanner"),
            [
                widget_tree.get_object("scanner_device"),
                widget_tree.get_object("scanner_resolution"),
                widget_tree.get_object("scanner_mode"),
                widget_tree.get_object("scanner_calibration"),
            ]
        )

        def refresh(*args, **kwargs):
            p = self._refresh_settings(widget_tree)
            p.schedule()

        def disable_refresh(*args, **kwargs):
            for c in self.config:
                self.core.call_all("config_remove_observer", c[0], refresh)

        for c in self.config:
            self.core.call_all("config_add_observer", c[0], refresh)

        global_widget_tree.get_object("settings_window").connect(
            "destroy", disable_refresh
        )

        list_settings_promise = self._refresh_settings(widget_tree)
        self.core.call_all(
            "complete_scanner_settings", widget_tree, list_settings_promise
        )
        list_settings_promise.schedule()

    def _translate_mode(self, mode):
        return {
            'Color': _("Color"),
            'Gray': _("Grayscale"),
            'Lineart': _("Black & White"),
        }[mode]

    def _refresh_settings(self, widget_tree):
        for (config_key, widget_name, default_value, fmt) in self.config:
            value = self.core.call_success("config_get", config_key)
            if value is None:
                value = default_value
            widget_tree.get_object(widget_name).set_text(fmt(value))

        def set_scanner_name(devs):
            active = self.core.call_success("config_get", "scanner_dev_id")
            for (dev_id, dev_name) in devs:
                if dev_id == active:
                    w = widget_tree.get_object('scanner_device_value')
                    w.set_text(dev_name)
                    break
            return devs

        promise = self.core.call_success("scan_list_scanners_promise")
        promise = promise.then(set_scanner_name)
        return promise
