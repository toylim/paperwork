import gettext
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_scan_buttons_popover_sources',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_scan_buttons_popover',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageadd.source_popover'
                ],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "mainloop_schedule", self.core.call_all,
            "pageadd_sources_refresh"
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def pageadd_get_sources(self, out: list):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageadd", "source_box.glade"
        )
        source_long_txt = _("Import image or PDF file(s)")
        source_short_txt = _("Import file(s)")
        img = "insert-image-symbolic"

        widget_tree.get_object("source_image").set_from_icon_name(
            img, Gtk.IconSize.SMALL_TOOLBAR
        )
        widget_tree.get_object("source_name").set_text(source_long_txt)

        out.append(
            (
                widget_tree.get_object("source_selector"),
                source_short_txt, "import", self._on_import
            )
        )

    def _on_import(self, doc_id, doc_url, source_id):
        # TODO
        pass
