import gettext
import logging

import pillowfight

import openpaperwork_core
import openpaperwork_core.promise


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.size_allocate_connect_id = None
        self.scan_height = 0
        self.scan_width = 0
        self.scan_img = None

    def get_interfaces(self):
        return [
            'gtk_settings_calibration',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_drawer_calibration',
                'defaults': ['paperwork_gtk.drawer.calibration'],
            },
            {
                'interface': 'gtk_drawer_pillow',
                'defaults': ['paperwork_gtk.drawer.pillow'],
            },
            {
                'interface': 'gtk_drawer_scan',
                'defaults': ['paperwork_gtk.drawer.scan'],
            },
            # Optional:
            # {
            #     'interface': 'gtk_zoomable',
            #     'defaults': [
            #         'paperwork_gtk.gesture.zoom',
            #         'paperwork_gtk.keyboard_shortcut.zoom',
            #     ],
            # },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_settings_dialog',
                'defaults': ['paperwork_gtk.settings'],
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

    def complete_settings(self, global_widget_tree):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings.scanner", "calibration.glade"
        )

        self.size_allocate_connect_id = self.widget_tree.get_object(
            "calibration_scroll"
        ).connect(
            "size-allocate", self._update_calibration_scroll_area_size
        )
        self.value_changed_connect_id = self.widget_tree.get_object(
            "calibration_scale_adjustment"
        ).connect(
            "value-changed", self._update_calibration_area_size_based_on_scale
        )

        self.widget_tree.get_object("calibration_back").connect(
            "clicked", self._hide_calibration_screen, global_widget_tree
        )
        self.widget_tree.get_object("calibration_scan").connect(
            "clicked", self._start_scan
        )
        self.widget_tree.get_object("calibration_maximize").connect(
            "clicked", self._on_maximize
        )
        self.widget_tree.get_object("calibration_automatic").connect(
            "clicked", self._on_automatic
        )

        drawing_area = self.widget_tree.get_object("calibration_area")
        self.core.call_all("draw_scan_start", drawing_area)

        self.core.call_all(
            "add_setting_screen",
            global_widget_tree,
            "calibration",
            self.widget_tree.get_object("calibration_header"),
            self.widget_tree.get_object("calibration_body"),
        )

    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        assert(self.widget_tree is not None)

        parent_widget_tree.get_object("scanner_calibration").connect(
            "clicked", self._display_calibration_screen, global_widget_tree
        )

    def on_settings_closed(self, global_widget_tree):
        drawing_area = self.widget_tree.get_object("calibration_area")
        self.core.call_all("draw_scan_stop", drawing_area)
        drawing_area.disconnect(self.value_changed_connect_id)
        self.widget_tree.get_object("calibration_scroll").disconnect(
            self.size_allocate_connect_id
        )

    def _display_calibration_screen(self, button, global_widget_tree):
        LOGGER.info("Switching to calibration screen")
        self.core.call_all(
            "show_setting_screen", global_widget_tree, "calibration"
        )

        sources = self.widget_tree.get_object("calibration_sources")
        sources.clear()
        sources.append(("", _("Loading ...")))

        combobox = self.widget_tree.get_object("calibration_source")
        combobox.set_active(0)
        combobox.set_sensitive(False)

        buttons = [
            'calibration_automatic',
            'calibration_maximize',
            'calibration_scan',
        ]
        for button in buttons:
            self.widget_tree.get_object(button).set_sensitive(False)

        self.core.call_all(
            "on_zoomable_widget_new",
            self.widget_tree.get_object("calibration_scroll"),
            self.widget_tree.get_object("calibration_scale_adjustment")
        )

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_busy",)
        )
        promise = promise.then(
            # drop the return value of call_all()
            lambda *args, **kwargs: None
        )
        promise = promise.then(self.core.call_success(
            "scan_get_scanner_promise"
        ))
        promise = promise.then(self._show_sources)
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_idle",)
        ))
        promise.schedule()

    def _show_sources(self, dev):
        sources = [
            (
                source.get_name(),
                self.core.call_success(
                    "i18n_scanner_source", source.get_name()
                ),
            )
            for source in dev.dev.get_children()
        ]
        LOGGER.info("Found %d sources", len(sources))

        sources_widget = self.widget_tree.get_object("calibration_sources")
        sources_widget.clear()
        for src in sources:
            LOGGER.info("Source: %s ; %s", src[0], src[1])
            sources_widget.append(src)

        combobox = self.widget_tree.get_object("calibration_source")
        combobox.set_active(0)
        combobox.set_sensitive(True)

        self.widget_tree.get_object("calibration_scan").set_sensitive(True)

    def _hide_calibration_screen(self, button, global_widget_tree):
        LOGGER.info("Switching back to settings")
        self.core.call_all("show_setting_screen", global_widget_tree, "main")
        self.core.call_all(
            "on_zoomable_widget_destroy",
            self.widget_tree.get_object("calibration_area"),
            self.widget_tree.get_object("calibration_scale_adjustment")
        )

    def _start_scan(self, button):
        combobox = self.widget_tree.get_object("calibration_source")
        source_idx = combobox.get_active()
        sources = self.widget_tree.get_object("calibration_sources")
        source = sources[source_idx][0]

        LOGGER.info("Starting calibration scan on %s ...", source)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_busy",)
        )
        # calibration is always done at 75 DPI
        promise = promise.then(
            self.core.call_success(
                "scan_promise", source_id=source, resolution=75
            )[1]
        )
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._scan
        ))
        promise = promise.then(self._on_scan_end)
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_idle",)
        ))
        promise.schedule()
        self.widget_tree.get_object("calibration_scan").set_sensitive(False)

    def _scan(self, args):
        (source, scan_id, img_generator) = args
        # just unroll the image generator.
        # --> we catch the content using the the on_scan_XXXX callbacks.
        img = None
        for (idx, img) in enumerate(img_generator):
            LOGGER.info("Page %d scanned: %s", idx, img.size)
        return img

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        self.scan_height = scan_params.get_height()
        self.scan_width = scan_params.get_width()
        self._update_calibration_area_size_based_on_scroll()
        self._update_calibration_scroll_area_size()

    def _update_calibration_area_size_based_on_scroll(self, *args, **kwargs):
        scroll = self.widget_tree.get_object("calibration_scroll")
        widget_height = scroll.get_allocated_height()
        factor = widget_height / self.scan_height
        self.widget_tree.get_object("calibration_scale_adjustment").set_value(
            factor
        )
        # signal 'value-changed' will trigger the update and redraw
        self.widget_tree.get_object("calibration_scale_adjustment").set_lower(
            factor
        )

    def _update_calibration_area_size_based_on_scale(self, *args, **kwargs):
        adj = self.widget_tree.get_object(
            "calibration_scale_adjustment"
        )
        factor = adj.get_value()
        LOGGER.debug(
            "Scale: %f < %f < %f", adj.get_lower(), factor, adj.get_upper()
        )

        widget_width = int(self.scan_width * factor)
        widget_height = int(self.scan_width * factor)

        LOGGER.debug(
            "Calibratrion widget size: (%d, %d)", widget_width, widget_height
        )
        self.widget_tree.get_object("calibration_area").set_size_request(
            widget_width, widget_height
        )
        self.widget_width = widget_width

    def _update_calibration_scroll_area_size(self, *args, **kwargs):
        # scroll area must have the same proportion than the scanned image
        scroll = self.widget_tree.get_object("calibration_scroll")
        widget_height = scroll.get_allocated_height()
        if self.scan_height <= 0:
            ratio = 1.0 / 1.414
        else:
            ratio = self.scan_width / self.scan_height
        widget_width = widget_height * ratio
        LOGGER.debug(
            "Calibration scroll window size: (%d, %d)",
            widget_width, widget_height
        )
        scroll.set_size_request(widget_width, -1)

        if self.scan_height > 0:
            factor = widget_height / self.scan_height
            adj = self.widget_tree.get_object("calibration_scale_adjustment")
            if adj.get_value() < factor:
                adj.set_value(factor)
            adj.set_lower(factor)

    def _on_scan_end(self, scan_img=None):
        buttons = [
            'calibration_automatic',
            'calibration_maximize',
            'calibration_scan'
        ]
        for button in buttons:
            self.widget_tree.get_object(button).set_sensitive(True)

        drawing_area = self.widget_tree.get_object("calibration_area")
        self.core.call_all("draw_scan_stop", drawing_area)

        if scan_img is None:
            LOGGER.info("No page scanned. Can't do calibration")
            return

        (self.scan_width, self.scan_height) = scan_img.size
        self.scan_img = scan_img

        self.core.call_all("draw_pillow_start", drawing_area, scan_img)
        self.core.call_all(
            "draw_calibration_start", drawing_area, scan_img.size
        )

        LOGGER.info("Calibration scan ready")

    def _on_maximize(self, button):
        if self.scan_height <= 0 or self.scan_width <= 0:
            return
        self.core.call_all(
            "config_put", "scanner_calibration",
            [0, 0, self.scan_width, self.scan_height]
        )

    def _on_automatic(self, button):
        if self.scan_img is None:
            return
        frame = pillowfight.find_scan_borders(self.scan_img)
        self.core.call_all("config_put", "scanner_calibration", list(frame))
