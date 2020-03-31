import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


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

    def on_vscroll_value_changed(self, vadj):
        super().on_vscroll_value_changed(vadj)
        self._update_visibility()

    def on_vscroll_changed(self, vadj):
        super().on_vscroll_changed(vadj)
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
        self.plugin.core.call_all(
            "doc_reload_page_component",
            components,
            self.plugin.active_doc[0],
            self.plugin.active_doc[1],
            page_idx
        )
        assert(len(components) <= 1)
        component = components[0] if len(components) >= 1 else None
        widget = self.plugin._build_flow_box_child(component.widget)
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
    def __init__(self, core, plugin):
        super().__init__(plugin)
        self.core = core
        self.nb_loaded = 0

        # page instantiation must be done before the calls to enter()
        # because other controllers may need the pages. So we cheat a little
        # bit and make it in the constructor.

        pages = []
        self.core.call_all(
            "doc_open_components", pages, *self.plugin.active_doc
        )

        for page in pages:
            widget = self.plugin._build_flow_box_child(page.widget)
            self.plugin.widget_to_page[widget] = page
            self.plugin.pages.append(page)
            self.plugin.page_layout.add(widget)

    def enter(self):
        super().enter()
        if len(self.plugin.pages) <= 0:
            self.plugin.docview_switch_controller(
                'layout', LayoutControllerLoaded
            )
            return
        self.nb_loaded = 0
        for page in self.plugin.pages:
            page.load()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self.nb_loaded += 1
        if self.nb_loaded >= len(self.plugin.pages):
            self.plugin.docview_switch_controller(
                'layout', LayoutControllerLoaded
            )

    def exit(self):
        LOGGER.info(
            "Size of all pages of doc %s loaded", self.plugin.active_doc[0]
        )


class LayoutControllerLoaded(BaseLayoutController):
    def enter(self):
        super().enter()
        self._update_visibility()


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['gtk_docview_controller']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['layout'] = LayoutControllerLoading(self.core, docview)
