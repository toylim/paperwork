import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 750

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.active_doc = None

    def get_interfaces(self):
        return [
            'gtk_doc_property',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'extra_text',
                'defaults': ['paperwork_backend.model.extra_text'],
            },
            {
                'interface': 'gtk_doc_properties',
                'defaults': ['paperwork_gtk.docproperties'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def _get_widget_text(self):
        text_buffer = self.widget_tree.get_object("doctext_text").get_buffer()
        start = text_buffer.get_iter_at_offset(0)
        end = text_buffer.get_iter_at_offset(-1)
        return text_buffer.get_text(start, end, False)

    def doc_properties_components_get(self, out: list):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "extra_text.glade"
        )

        out.append(self.widget_tree.get_object("doctext"))

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)
        txt = []
        self.core.call_all("doc_get_extra_text_by_url", txt, doc_url)
        txt = "\n".join(txt)
        self.widget_tree.get_object("doctext_text").get_buffer().set_text(txt)

    def doc_properties_components_apply_changes(self, out):
        orig_txt = []
        self.core.call_all(
            "doc_get_extra_text_by_url", orig_txt, self.active_doc[1]
        )
        orig_txt = "\n".join(orig_txt).strip()

        new_txt = self._get_widget_text()

        if new_txt == orig_txt:
            return

        LOGGER.info(
            "Extra keywords have been changed in document %s",
            self.active_doc[0]
        )
        self.core.call_all(
            "doc_set_extra_text_by_url", self.active_doc[1], new_txt
        )

        out.upd_docs.add(self.active_doc[0])

    def doc_properties_components_cancel_changes(self):
        self.doc_properties_components_set_active_doc(*self.active_doc)
