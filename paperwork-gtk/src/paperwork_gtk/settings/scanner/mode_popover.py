import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    RECOMMENDED = 300
    MODES = [
        ('radioColor', 'Color'),
        ('radioGrayscale', 'Gray'),
        ('radioLineart', 'Lineart'),
    ]

    def get_interfaces(self):
        return [
            'gtk_settings_scanner_setting',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_settings_scanner',
                'defaults': ['paperwork_gtk.settings.scanner.settings'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings.scanner",
            "popover_mode.glade"
        )

        active = self.core.call_success("config_get", "scanner_mode")
        for (widget, mode) in self.MODES:
            if mode == active:
                widget_tree.get_object(widget).set_active(True)

        for (widget, mode) in self.MODES:
            widget_tree.get_object(widget).connect(
                "toggled", self._on_toggle,
                widget_tree, mode
            )

        selector = widget_tree.get_object("selector")
        parent_widget_tree.get_object("scanner_mode").set_popover(selector)

    def _on_toggle(self, checkbox, widget_tree, mode):
        LOGGER.info("Selected mode: %s", mode)
        widget_tree.get_object("selector").popdown()
        self.core.call_success("config_put", "scanner_mode", mode)
