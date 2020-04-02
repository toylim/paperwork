import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class BaseLayoutController(BaseDocViewController):
    def __init__(self, core, plugin):
        super().__init__(plugin)
        self.core = core
        self.real_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.plugin.active_doc[1]
        )
        if self.real_nb_pages is None:
            self.real_nb_pages = 0

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

    def _doc_remove_page(self, page_idx):
        LOGGER.info("Removing page %d from layout", page_idx)
        for widget in list(self.plugin.page_layout.get_children()):
            page = self.plugin.widget_to_page[widget]
            if page.page_idx == page_idx:
                self.plugin.widget_to_page.pop(widget)
                self.plugin.page_layout.remove(widget)
                self.plugin.pages.remove(page)

    def _doc_add_page(self, page_idx):
        LOGGER.info("Adding page %d to layout", page_idx)
        components = []
        self.core.call_all(
            "doc_reload_page_component",
            components,
            self.plugin.active_doc[0],
            self.plugin.active_doc[1],
            page_idx
        )
        assert(len(components) <= 1)
        component = components[0] if len(components) >= 1 else None
        widget = self.plugin._build_flow_box_child(component.widget)
        self.plugin.pages.insert(page_idx, component)
        self.plugin.widget_to_page[widget] = component
        self.plugin.page_layout.insert(widget, page_idx)
        component.set_zoom(self.plugin.zoom)
        component.load()

    def _doc_reload_for_removed_page(
            self, start_page_idx, old_nb_pages, new_nb_pages):
        # remove all pages that are probably obsolete
        # Keep in mind we cannot simply remove all the page after
        # start_page_idx because some plugins add 'fake' page widgets (see
        # scanview for instance). And those 'fake' widgets must remain.
        for page_idx in range(start_page_idx, old_nb_pages):
            self._doc_remove_page(page_idx)

        # rebuild the pages
        for page_idx in range(start_page_idx, new_nb_pages):
            self._doc_add_page(page_idx)

    def doc_reload_page(self, page_idx):
        super().doc_reload_page(page_idx)

        LOGGER.info("Reloading page %d", page_idx)

        real_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.plugin.active_doc[1]
        )
        if real_nb_pages is None:
            real_nb_pages = 0

        if real_nb_pages < self.real_nb_pages:
            LOGGER.info(
                "Number of pages has decreased (%d < %d)",
                real_nb_pages, self.real_nb_pages
            )
            # the number of pages has been reduced --> assume that page_idx
            # has been deleted
            self._doc_reload_for_removed_page(
                page_idx, self.real_nb_pages, real_nb_pages
            )
            return

        self._doc_remove_page(page_idx)
        self._doc_add_page(page_idx)
        self.real_nb_pages = real_nb_pages


class LayoutControllerLoading(BaseLayoutController):
    def __init__(self, core, plugin):
        super().__init__(core, plugin)
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
                'layout',
                lambda plugin: LayoutControllerLoaded(self.core, plugin)
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
