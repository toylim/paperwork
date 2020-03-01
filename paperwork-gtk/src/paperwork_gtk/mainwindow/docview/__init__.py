import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    LAYOUTS = {
        # name: pages per line (columns)
        'paged': 1,
        'grid': 3,
    }
    MAX_PAGES = max(LAYOUTS.values())

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.scroll = None
        self.active_doc = ()
        self.active_page_idx = 0
        self.target_page_idx = -1
        self.page_container = None
        self.pages = []
        self.page_widgets = {}
        self.nb_columns = self.MAX_PAGES
        self._last_scroll = 0  # to avoid multiple calls
        self._last_nb_columns = -1  # to avoid multiple calls
        self._last_zoom_auto = -1

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_open',
            'gtk_docview',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_widget_flowlayout',
                'defaults': ['paperwork_gtk.widget.flowlayout'],
            },
            {
                'interface': 'gtk_zoomable',
                'defaults': [
                    'paperwork_gtk.gesture.zoom',
                    'paperwork_gtk.keyboard_shortcut.zoom',
                ],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview", "docview.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.scroll = self.widget_tree.get_object("docview_scroll")

        self.page_container = self.core.call_success(
            "gtk_widget_flowlayout_new", spacing=(20, 20),
            scrollbars=self.scroll
        )
        self.page_container.connect(
            "widget_visible", self._upd_current_page_idx
        )
        self.page_container.connect(
            "widget_hidden", self._upd_current_page_idx
        )
        self.page_container.connect("layout_rearranged", self._upd_layout)
        self.page_container.set_visible(True)

        self.scroll.add(self.page_container)

        self.core.call_all(
            "mainwindow_add", side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

        self._upd_layout()

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def docview_set_zoom_adjustment(self, adj):
        self.core.call_all(
            "on_zoomable_widget_new",
            self.widget_tree.get_object("docview_scroll"), adj
        )

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_body")

    def doc_close(self):
        self._last_scroll = -1
        self.page_widgets = {}
        self.pages = []

        for child in self.page_container.get_children():
            self.page_container.remove(child)

    def doc_open(self, doc_id, doc_url):
        self.nb_columns = self.MAX_PAGES

        if len(self.pages) > 0:
            self.doc_close()

        self.active_doc = (doc_id, doc_url)

        self.core.call_all("on_memleak_track_stop")
        self.core.call_all("on_memleak_track_start")

        self.core.call_all(
            "doc_open_components",
            self.pages, doc_id, doc_url, self.page_container
        )

        for page in self.pages:
            page.connect("size_obtained", self._on_page_size_obtained)

        for page in self.pages:
            self.page_widgets[page.widget] = page
            self.page_container.add_child(page.widget, Gtk.Align.CENTER)

        self.doc_goto_page(0)

    def on_page_shown(self, page_idx):
        LOGGER.info("Active page %d", page_idx)
        self.active_page_idx = page_idx

    def _upd_current_page_idx(self, *args, **kwargs):
        # figure out the current page: the current page is one the in the
        # middle of the window
        p_scroll = (0, self.scroll.get_vadjustment().get_value())

        if p_scroll[1] == self._last_scroll:
            return
        self._last_scroll = p_scroll[1]

        p_size = self.scroll.get_allocation()

        p = (
            (p_size.width / 2) + p_scroll[0],
            (p_size.height / 2) + p_scroll[1]
        )
        widget = self.page_container.get_widget_at(p[0], p[1])

        if widget is None:
            # fall back on the top of the screen (there may not be enough pages
            # to fill the window)
            p = ((p_size.width / 2) + p_scroll[0], p_scroll[1])
            widget = self.page_container.get_widget_at(p[0], p[1])

        if widget is None:
            # really no pages
            return

        page_idx = self.page_widgets[widget].page_idx
        if self.active_page_idx != page_idx and page_idx >= 0:
            self.core.call_all("on_page_shown", page_idx)

    def docview_get_active_doc(self):
        return self.active_doc

    def docview_get_active_page(self):
        return self.active_page_idx

    def doc_goto_previous_page(self):
        self.doc_goto_page(self.active_page_idx - 1)

    def doc_goto_next_page(self):
        self.doc_goto_page(self.active_page_idx + 1)

    def doc_goto_page(self, page_idx):
        assert(page_idx >= 0)
        self.target_page_idx = page_idx

        if len(self.pages) <= 0:
            self.scroll.get_vadjustment().set_value(0)
            self.core.call_all("on_page_shown", 0)
            return False

        if page_idx < 0:
            page_idx = 0
        if page_idx >= len(self.pages):
            page_idx = len(self.pages) - 1
        LOGGER.info(
            "Going to page %d/%d (original: %d)",
            page_idx, len(self.pages), self.target_page_idx
        )

        self.core.call_all("on_page_shown", page_idx)

        widget = self.pages[page_idx].widget
        if widget is None:
            LOGGER.warning("No widget yet for page %d", page_idx)
            return False

        w_height = self.page_container.get_widget_position(widget)[1]
        if w_height < 0:
            LOGGER.warning("Failed to get widget height of page %d", page_idx)
            return False
        if self.scroll.get_vadjustment().get_value() != w_height:
            self.scroll.get_vadjustment().set_value(w_height)
            self._last_scroll = w_height
        return True

    def _upd_layout(self, *args, **kwargs):
        nb_columns = self.page_container.get_max_nb_columns()

        if nb_columns == self._last_nb_columns:
            return
        self._last_nb_columns = nb_columns

        # find the closest layout
        max_columns = -1
        layout_name = "paged"
        for (l_name, required_columns) in self.LAYOUTS.items():
            if nb_columns < required_columns:
                continue
            if max_columns >= required_columns:
                continue
            max_columns = required_columns
            layout_name = l_name

        self.core.call_all("on_layout_change", layout_name)

    def _rearrange_pages(self, nb_columns):
        layout_width = self.page_container.get_width_without_margins(
            nb_columns
        )
        if layout_width is None or len(self.pages) <= 0:
            return

        page_widths = 0
        for page_idx in range(0, len(self.pages), nb_columns):
            pages = self.pages[page_idx:page_idx + nb_columns]
            page_widths = max(
                page_widths, sum([p.get_full_size()[0] for p in pages])
            )

        zoom = layout_width / page_widths
        LOGGER.info(
            "Page widths = %s ==> Zoom: %d / %d = %f",
            page_widths, layout_width, page_widths, zoom
        )

        if zoom != self._last_zoom_auto:
            self._last_zoom_auto = zoom
            self.core.call_all("doc_view_set_zoom", zoom)

    def doc_view_set_layout(self, name):
        self.nb_columns = self.LAYOUTS[name]
        self._rearrange_pages(self.nb_columns)

    def doc_view_set_default_zoom(self, page, *args, **kwargs):
        self._rearrange_pages(self.nb_columns)

    def _on_page_size_obtained(self, page):
        if page.page_idx % 50 == 0:
            self.doc_view_set_default_zoom(page)
        elif page.page_idx >= len(self.pages) - self.MAX_PAGES:
            self.doc_view_set_default_zoom(page)

        if page.page_idx != self.target_page_idx:
            return
        target_page_idx = page.page_idx

        # page container will be resized
        # once it's resized, we want to jump back to the active page

        handler_id = None

        def scroll_on_resize(*args, **kwargs):
            if page.widget.get_allocated_height() <= 1:
                return
            if self.doc_goto_page(target_page_idx):
                self.page_container.disconnect(handler_id)
            self.target_page_idx = -1

        handler_id = self.page_container.connect(
            "size-allocate", scroll_on_resize
        )

    def doc_view_get_zoom(self):
        if len(self.pages) <= 0:
            return 1.0
        return self.pages[0].get_zoom()

    def doc_view_set_zoom(self, zoom):
        for page in self.pages:
            page.set_zoom(zoom)
        self.page_container.recompute_layout()

    def doc_reload(self, doc_id, doc_url):
        if doc_id != self.active_doc[0]:
            return

        if self.target_page_idx >= 0:
            active_page = self.target_page_idx
        else:
            active_page = self.active_page_idx
        active_doc = self.active_doc
        nb_columns = self.nb_columns

        self.doc_close()
        self.doc_open(*active_doc)
        self.nb_columns = nb_columns
        self.doc_goto_page(active_page)

    def docview_set_bottom_margin(self, height):
        self.page_container.set_bottom_margin(height)
