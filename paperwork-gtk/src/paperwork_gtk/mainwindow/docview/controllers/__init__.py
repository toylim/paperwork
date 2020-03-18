import logging


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

    def on_vscroll(self, vadj):
        LOGGER.debug(
            "%s(%d, %d)",
            self.on_vscroll,
            vadj.get_value(),
            vadj.get_upper()
        )

    def on_vscroll_changed(self, vadj):
        self.on_vscroll(vadj)

    def on_vscroll_value_changed(self, vadj):
        self.on_vscroll(vadj)

    def doc_goto_page(self, page_idx):
        LOGGER.debug("%s(%d)", self.doc_goto_page, page_idx)

    def docview_set_layout(self, name):
        LOGGER.debug("%s(%s)", self.docview_set_layout, name)

    def docview_set_zoom(self, zoom):
        LOGGER.debug("%s(%f)", self.docview_set_zoom, zoom)

    def doc_reload_page(self, page_idx):
        LOGGER.debug("%s()", self.doc_reload_page)

    def on_page_activated(self, page):
        LOGGER.debug("%s(%d)", self.on_page_activated, page.page_idx)
