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
        self.controllers = {}
        self.widget_tree = None
        self.scroll = None
        self.page_layout = None
        self.pages = []
        self.widget_to_page = {}
        self.nb_columns = self.MAX_PAGES

        self.zoom = 0.0
        self.layout_name = None
        self.requested_page_idx = 0

        self.active_page_idx = 0
        self.active_doc = (None, None)

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_open',
            'drag_and_drop_destination',
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
                'interface': 'gtk_zoomable',
                'defaults': [
                    'paperwork_gtk.gesture.zoom',
                    'paperwork_gtk.keyboard_shortcut.zoom',
                ],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.docview", "docview.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview", "docview.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.scroll = self.widget_tree.get_object("docview_scroll")
        self.scroll.get_vadjustment().connect(
            "value-changed", self._on_vscroll_value_changed
        )
        self.scroll.get_vadjustment().connect(
            "changed", self._on_vscroll_changed
        )

        self.overlay = self.widget_tree.get_object("docview_drawingarea")
        self.overlay.connect("draw", self._on_overlay_draw)

        self.page_layout = self.widget_tree.get_object("docview_page_layout")
        self.page_layout.connect(
            "size-allocate", self._on_layout_size_allocate
        )
        self.page_layout.connect("child-activated", self._on_child_activated)

        self.page_layout.connect("drag-motion", self._on_drag_motion)
        self.page_layout.connect("drag-leave", self._on_drag_leave)
        self.page_layout.connect("draw", self._on_draw)

        self.core.call_all(
            "mainwindow_add", side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_gtk_docview_init", self
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _on_child_activated(self, page_layout, child):
        page = self.widget_to_page[child]
        for controller in self.controllers.values():
            controller.on_page_activated(page)

    def docview_set_bottom_margin(self, height):
        self.widget_tree.get_object("docview_padding").set_size_request(
            1, height + 10
        )

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_body")

    def docview_get_scrollwindow(self):
        return self.widget_tree.get_object("docview_scroll")

    def docview_switch_controller(self, name, new_controller_ctor):
        self.controllers[name].exit()
        new_controller = new_controller_ctor(self)
        LOGGER.info(
            "%s: %s --> %s",
            name, str(self.controllers[name]), str(new_controller)
        )
        self.controllers[name] = new_controller
        new_controller.enter()

    def _on_layout_size_allocate(self, layout, allocation):
        for controller in self.controllers.values():
            controller.on_layout_size_allocate(layout)

    def _on_vscroll_value_changed(self, vadj):
        for controller in self.controllers.values():
            controller.on_vscroll_value_changed(vadj)

    def _on_vscroll_changed(self, vadj):
        for controller in self.controllers.values():
            controller.on_vscroll_changed(vadj)

    def _on_drag_motion(self, layout, drag_context, x, y, time):
        for controller in self.controllers.values():
            controller.on_drag_motion(drag_context, x, y, time)

    def _on_drag_leave(self, layout, drag_context, time):
        for controller in self.controllers.values():
            controller.on_drag_leave(drag_context, time)

    def drag_and_drop_get_destination(self, widget, x, y):
        if widget != self.page_layout:
            return None
        for controller in self.controllers.values():
            r = controller.drag_and_drop_get_destination(x, y)
            if r is not None:
                return r
        return None

    def _on_draw(self, layout, cairo_context):
        for controller in self.controllers.values():
            controller.on_draw(cairo_context)

    def _on_overlay_draw(self, widget, cairo_context):
        for controller in self.controllers.values():
            controller.on_overlay_draw(widget, cairo_context)

    def doc_close(self):
        for controller in self.controllers.values():
            controller.exit()
        for page in self.page_layout.get_children():
            self.page_layout.remove(page)
        for page in self.pages:
            page.set_visible(False)
        self.pages = []
        self.widget_to_page = {}

    def _build_flow_box_child(self, child):
        widget = Gtk.FlowBoxChild.new()
        widget.set_visible(True)
        widget.set_property('halign', Gtk.Align.CENTER)
        widget.add(child)
        return widget

    def doc_open(self, doc_id, doc_url):
        self.doc_close()

        self.core.call_all("mainwindow_show", side="right", name="docview")

        self.zoom = 0.0
        self.layout_name = 'grid'
        self.active_doc = (doc_id, doc_url)
        self.active_page_idx = 0

        self.pages = []
        self.widget_to_page = {}

        self.controllers = {}
        self.core.call_all(
            "gtk_docview_get_controllers", self.controllers, self
        )

        for controller in self.controllers.values():
            controller.enter()

    def on_page_size_obtained(self, page):
        # page may been wrapped
        page = self.pages[page.page_idx]
        for controller in self.controllers.values():
            controller.on_page_size_obtained(page)

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def doc_goto_previous_page(self):
        self.doc_goto_page(self.active_page_idx - 1)

    def doc_goto_next_page(self):
        self.doc_goto_page(self.active_page_idx + 1)

    def doc_goto_page(self, page_idx):
        LOGGER.info("Going to page %d", page_idx)
        if page_idx < 0:
            page_idx = 0
        self.requested_page_idx = page_idx
        for controller in self.controllers.values():
            controller.doc_goto_page(page_idx)

    def docview_set_layout(self, name):
        self.layout_name = name
        for controller in self.controllers.values():
            controller.docview_set_layout(name)

    def docview_set_zoom(self, zoom):
        self.zoom = zoom
        for controller in self.controllers.values():
            controller.docview_set_zoom(zoom)

    def doc_reload_page(self, doc_id, doc_url, page_idx):
        if self.active_doc[0] != doc_id:
            return
        LOGGER.info("Reloading page %d of document %s", page_idx, doc_id)
        for controller in self.controllers.values():
            controller.doc_reload_page(page_idx)
