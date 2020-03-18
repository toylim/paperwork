import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


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

    def on_vscroll_changed(self, vadj):
        super().on_vscroll_changed(vadj)
        self._update_current_page()

    def on_vscroll_value_changed(self, vadj):
        super().on_vscroll_value_changed(vadj)
        self._update_current_page()


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
        out['page_number'] = PageNumberController(docview)
