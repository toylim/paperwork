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
        self.page_info = None
        self.nb_pages = None
        self.current_page = None
        self.layout_icon = None
        self.layout_button = None
        self.nb_pages = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_docview_pageinfo',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
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

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.page_info = self.widget_tree.get_object("page_info")
        self.layout_icon = self.widget_tree.get_object("page_layout_icon")
        self.current_page = self.widget_tree.get_object("page_current_nb")
        self.current_page.connect("activate", self._change_page)
        self.layout_button = self.widget_tree.get_object("page_layout")
        self.nb_pages = self.widget_tree.get_object("page_total")

        self.layout_button.connect("clicked", self._open_layout_menu)

        button = self.widget_tree.get_object("page_prev")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all(
                "doc_goto_previous_page"
            )
        )
        button = self.widget_tree.get_object("page_next")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all("doc_goto_next_page")
        )

        self.core.call_success("docview_get_body").add_overlay(self.page_info)

    def _change_page(self, *args, **kwargs):
        txt = self.current_page.get_text()
        if txt == "":
            return
        self.core.call_all("doc_goto_page", int(txt) - 1)

    def doc_open(self, doc_id, doc_url):
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            LOGGER.warning("Failed to get the number of pages in %s", doc_id)
            nb_pages = 0

        self.nb_pages.set_text(f"/ {nb_pages}")
        self.page_info.set_visible(True)

    def on_page_shown(self, page_idx):
        txt = str(page_idx + 1)
        if txt != self.current_page.get_text():
            self.current_page.set_text(txt)

    def on_layout_change(self, layout_name):
        if self.layout_icon is None:
            return

        icon = self.LAYOUTS[layout_name]['icon']
        # smallest icon size available
        self.layout_icon.set_from_icon_name(icon, Gtk.IconSize.SMALL_TOOLBAR)

    def set_zoom(self, factor):
        pass

    def _open_layout_menu(self, *args, **kwargs):
        pass
