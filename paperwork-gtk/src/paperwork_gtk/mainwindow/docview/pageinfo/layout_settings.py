import logging

import openpaperwork_core
import openpaperwork_gtk.deps


try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    LAYOUTS = {
        'inline': {
            'icon': 'view-paged-symbolic',
        },
        'grid': {
            'icon': 'view-grid-symbolic',
        },
    }

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.layout_icon = None
        self.layout_button = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_layout_settings',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_docview_pageinfo',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageinfo'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageinfo",
            "layout_settings.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.layout_icon = self.widget_tree.get_object("page_layout_icon")
        self.layout_button = self.widget_tree.get_object("page_layout")
        self.layout_button.connect("clicked", self._open_layout_menu)

        self.core.call_success("page_info_add_left", self.layout_button)

    def on_layout_change(self, layout_name):
        if self.layout_icon is None:
            return

        icon = self.LAYOUTS[layout_name]['icon']
        # smallest icon size available
        self.layout_icon.set_from_icon_name(icon, Gtk.IconSize.SMALL_TOOLBAR)

    def _open_layout_menu(self, *args, **kwargs):
        menu = self.widget_tree.get_object("layout_settings")
        menu.set_relative_to(self.layout_button)
        menu.set_visible(True)
