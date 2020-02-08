import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'gtk_settings_scanner_dev_id',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_settings_scanner',
                'defaults': ['paperwork_gtk.settings.scanner.settings'],
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

    def complete_scanner_settings(
            self, settings_widget_tree,
            list_scanner_promise):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings.scanner.dev_id_selector",
            "dev_id_selector.glade"
        )

        widget_tree.get_object("settings_stack").set_visible_child_name(
            "spinner"
        )
        widget_tree.get_object("spinner").start()

        settings_widget_tree.get_object("scanner_device").set_popover(
            widget_tree.get_object("scanner_dev_id_selector")
        )

        list_scanner_promise.then(self._on_scanner_list, widget_tree)

    def _on_scanner_list(self, devs, widget_tree):
        widget_tree.get_object("spinner").stop()
        widget_tree.get_object("settings_stack").set_visible_child_name(
            "dev_id_selector"
        )
        box = widget_tree.get_object("scanner_dev_id_selector_box")

        radios = []
        for dev in devs:
            radio = self.core.call_success(
                "gtk_load_widget_tree", "paperwork_gtk.settings.scanner",
                "dev_id_selector_box.glade"
            )
            radio = radio.get_object("scanner_dev_id_radio")
            radio.set_label(dev[1])
            box.pack_start(radio, expand=False, fill=True, padding=0)
            radios.append((dev[0], radio))

        for (dev_id, radio) in radios[1:]:
            radio.join_group(radios[0][1])

        active = self.core.call_success("config_get", "scanner_dev_id")
        for (dev_id, radio) in radios:
            if active == dev_id:
                radio.set_active(True)

        for (dev_id, radio) in radios:
            radio.connect(
                "toggled", self._on_toggle,
                widget_tree, dev_id, radio.get_label()
            )

    def _on_toggle(
            self, checkbox, widget_tree, dev_id, dev_name):
        LOGGER.info("Selected scanner: %s - %s", dev_id, dev_name)
        widget_tree.get_object("scanner_dev_id_selector").popdown()
        active = self.core.call_success("config_put", "scanner_dev_id", dev_id)