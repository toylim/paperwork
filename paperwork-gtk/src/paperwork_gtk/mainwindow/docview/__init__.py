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


class BaseDocViewController(object):
    def __init__(self, plugin):
        self.plugin = plugin

    def __str__(self):
        return str(type(self))

    def enter(self):
        LOGGER.debug("%s", self.enter)

    def exit(self):
        LOGGER.debug("%s", self.exit)

    def on_layout_size_allocate(self, layout):
        LOGGER.debug("%s(%s)", self.on_layout_size_allocate, layout)

    def on_page_size_obtained(self, page):
        LOGGER.debug("%s(%d)", self.on_page_size_obtained, page.page_idx)

    def on_vscroll(self, vadjustment):
        LOGGER.debug(
            "%s(%d, %d)",
            self.on_vscroll,
            vadjustment.get_value(),
            vadjustment.get_upper()
        )

    def doc_goto_page(self, page_idx):
        LOGGER.debug("%s(%d)", self.doc_goto_page, page_idx)

    def docview_set_layout(self, name):
        LOGGER.debug("%s(%s)", self.docview_set_layout, name)

    def docview_set_zoom(self, zoom):
        LOGGER.debug("%s(%f)", self.docview_set_zoom, zoom)

    def doc_reload_page(self, page_id):
        LOGGER.debug("%s()", self.doc_reload_page)


class BaseLayoutController(BaseDocViewController):
    def _update_visibility(self):
        vadj = self.plugin.scroll.get_vadjustment()
        lower = vadj.get_lower()
        p_min = vadj.get_value() - lower
        p_max = vadj.get_value() + vadj.get_page_size() - lower
        for widget in self.plugin.page_layout.get_children():
            alloc = widget.get_allocation()
            p_lower = alloc.y
            p_upper = alloc.y + alloc.height
            visible = (p_min <= p_upper and p_lower <= p_max)
            page = self.plugin.widget_to_page[widget]
            page.set_visible(visible)

    def on_vscroll(self, vadj):
        super().on_vscroll(vadj)
        self._update_visibility()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self._update_visibility()

    def on_layout_size_allocate(self, layout):
        super().on_layout_size_allocate(layout)
        self._update_visibility()

    def doc_reload_page(self, page_idx):
        super().doc_reload_page(page_idx)
        for widget in list(self.plugin.page_layout.get_children()):
            page = self.plugin.widget_to_page[widget]
            if page.page_idx == page_idx:
                self.plugin.widget_to_page.pop(widget)
                self.plugin.page_layout.remove(widget)
        components = []
        self.plugin.core.call_success(
            "doc_reload_page_component",
            components,
            self.plugin.active_doc[0],
            self.plugin.active_doc[1],
            page_idx
        )
        assert(len(components) <= 1)
        component = components[0] if len(components) >= 1 else None
        widget = self.plugin._get_flow_box_child(component.widget)
        if component is None:
            if page_idx < len(self.plugin.pages):
                self.plugin.pages.pop(page_idx)
            return
        if page_idx < len(self.plugin.pages):
            self.plugin.pages[page_idx] = component
        elif page_idx == len(self.plugin.pages):
            self.plugin.pages.append(component)
        else:
            assert()
        self.plugin.widget_to_page[widget] = component
        self.plugin.page_layout.insert(widget, page_idx)
        component.set_zoom(self.plugin.zoom)
        component.load()


class LayoutControllerLoading(BaseLayoutController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.nb_loaded = 0

    def enter(self):
        super().enter()
        if len(self.plugin.pages) <= 0:
            self.plugin._switch_controller('layout', LayoutControllerLoaded)
            return
        self.nb_loaded = 0
        for page in self.plugin.pages:
            page.load()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self.nb_loaded += 1
        if self.nb_loaded >= len(self.plugin.pages):
            self.plugin._switch_controller('layout', LayoutControllerLoaded)

    def exit(self):
        LOGGER.info(
            "Size of all pages of doc %s loaded", self.plugin.active_doc[0]
        )


class LayoutControllerLoaded(BaseLayoutController):
    def enter(self):
        super().enter()
        self._update_visibility()


class PageNumberController(BaseDocViewController):
    def _update_current_page(self):
        vadj = self.plugin.scroll.get_vadjustment()
        view_width = self.plugin.scroll.get_allocated_width()
        view_height = self.plugin.scroll.get_allocated_height()
        center = (
            view_width / 2,
            vadj.get_value() + (view_height / 2)
        )

        min_dist = (99999999999999999, None)
        for widget in self.plugin.page_layout.get_children():
            alloc = widget.get_allocation()
            widget_center = (
                (alloc.x + (alloc.width / 2)),
                (alloc.y + (alloc.height / 2)),
            )
            dist_w = (center[0] - widget_center[0])
            dist_h = (center[1] - widget_center[1])
            dist = (dist_w * dist_w) + (dist_h * dist_h)
            if dist < min_dist[0]:
                min_dist = (dist, widget)

        if min_dist[1] is None:
            return

        page = self.plugin.widget_to_page[min_dist[1]]
        self.plugin.core.call_all("on_page_shown", page.page_idx)

    def on_layout_size_allocate(self, layout):
        super().on_layout_size_allocate(layout)
        self._update_current_page()

    def on_page_size_obtained(self, layout):
        super().on_page_size_obtained(layout)
        self._update_current_page()

    def doc_goto_page(self, page_idx):
        super().doc_goto_page(page_idx)
        for widget in self.plugin.page_layout.get_children():
            page = self.plugin.widget_to_page[widget]
            if page.page_idx != page_idx:
                continue
            alloc = widget.get_allocation()
            self.plugin.scroll.get_vadjustment().set_value(alloc.y)
            break

    def on_vscroll(self, layout):
        super().on_vscroll(layout)
        self._update_current_page()


class ZoomLayoutController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.last_zoom = -1

    def _recompute_zoom(self):
        layout_name = self.plugin.layout_name
        spacing = self.plugin.page_layout.get_column_spacing()
        nb_columns = self.plugin.LAYOUTS[layout_name]
        max_columns = 0
        view_width = self.plugin.scroll.get_allocated_width()
        zoom = 1.0
        for page_idx in range(0, len(self.plugin.pages), nb_columns):
            pages = self.plugin.pages[page_idx:page_idx + nb_columns]
            pages_width = sum([p.get_full_size()[0] for p in pages])
            pages_width += (len(pages) * 30 * spacing) + 1
            zoom = min(zoom, view_width / pages_width)
            max_columns = max(max_columns, len(pages))

        if zoom == self.last_zoom:
            return
        self.last_zoom = zoom

        self.plugin.core.call_all("docview_set_zoom", zoom)
        for page in self.plugin.pages:
            page.set_zoom(zoom)

        layout = (-1, 'paged')
        for (layout_name, nb_columns) in self.plugin.LAYOUTS.items():
            if nb_columns <= layout[0]:
                continue
            if max_columns >= nb_columns:
                layout = (nb_columns, layout_name)
        self.plugin.core.call_all("on_layout_change", layout[1])

    def enter(self):
        super().enter()
        self._recompute_zoom()

    def docview_set_zoom(self, zoom):
        super().docview_set_zoom(zoom)
        if zoom == self.last_zoom:
            return
        self.plugin._switch_controller('zoom', ZoomCustomController)

    def docview_set_layout(self, name):
        super().docview_set_layout(name)
        self._recompute_zoom()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self._recompute_zoom()

    def on_layout_size_allocate(self, layout):
        self._recompute_zoom()


class ZoomCustomController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.scroll_proportion = None

    def _reapply_zoom(self):
        vadj = self.plugin.scroll.get_vadjustment()
        self.scroll_proportion = vadj.get_value() / vadj.get_upper()

        zoom = self.plugin.zoom
        for page in self.plugin.pages:
            page.set_zoom(zoom)

    def enter(self):
        super().enter()
        self._reapply_zoom()

    def docview_set_zoom(self, zoom):
        super().docview_set_zoom(zoom)
        self._reapply_zoom()

    def docview_set_layout(self, name):
        super().docview_set_layout(name)
        self.plugin._switch_controller('zoom', ZoomLayoutController)

    def on_vscroll(self, adj):
        if self.scroll_proportion is None:
            return
        pos = self.scroll_proportion * adj.get_upper()
        self.scroll_proportion = None
        adj.set_value(pos)


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
        self.scroll.get_vadjustment().connect(
            "value-changed", self._on_vscroll
        )
        self.scroll.get_vadjustment().connect("changed", self._on_vscroll)

        self.page_layout = self.widget_tree.get_object("docview_page_layout")
        self.page_layout.connect(
            "size-allocate", self._on_layout_size_allocate
        )

        self.core.call_all(
            "mainwindow_add", side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def docview_set_bottom_margin(self, height):
        # TODO
        # self.page_layout.set_bottom_margin(height)
        pass

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_body")

    def docview_get_scrollwindow(self):
        return self.widget_tree.get_object("docview_scroll")

    def _switch_controller(self, name, new_controller_ctor):
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

    def _on_vscroll(self, vadj):
        for controller in self.controllers.values():
            controller.on_vscroll(vadj)

    def doc_close(self):
        for controller in self.controllers.values():
            controller.exit()
        for page in self.page_layout.get_children():
            self.page_layout.remove(page)
        self.pages = []
        self.widget_to_page = {}

    def _get_flow_box_child(self, child):
        widget = Gtk.FlowBoxChild.new()
        widget.set_visible(True)
        widget.set_property('halign', Gtk.Align.CENTER)
        widget.add(child)
        return widget

    def doc_open(self, doc_id, doc_url):
        self.doc_close()

        self.controllers = {
            'layout': LayoutControllerLoading(self),
            'page_number': PageNumberController(self),
            'zoom': ZoomLayoutController(self),
        }
        self.zoom = 0.0
        self.layout_name = 'grid'
        self.active_doc = (doc_id, doc_url)
        self.active_page_idx = 0

        self.pages = []
        self.widget_to_page = {}

        pages = []
        self.core.call_all("doc_open_components", pages, doc_id, doc_url)

        for page in pages:
            widget = self._get_flow_box_child(page.widget)
            self.widget_to_page[widget] = page
            self.pages.append(page)
            self.page_layout.add(widget)

        for controller in self.controllers.values():
            controller.enter()

    def on_page_size_obtained(self, page):
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
