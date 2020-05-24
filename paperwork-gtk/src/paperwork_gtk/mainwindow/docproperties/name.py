import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_calendar_popover',
                'defaults': ['openpaperwork_gtk.widgets.calendar'],
            },
            {
                'interface': 'gtk_doc_properties',
                'defaults': ['paperwork_gtk.docproperties'],
            },
            {
                'interface': 'gtk_colors',
                'defaults': ['openpaperwork_gtk.colors'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def doc_properties_components_get(self, out: list, multiple_docs=False):
        if multiple_docs:
            return
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "name.glade"
        )

        self.core.call_all(
            "gtk_calendar_add_popover",
            self.widget_tree.get_object("docname_entry")
        )

        self.widget_tree.get_object("docname_entry").connect(
            "changed", self._on_doc_date_changed
        )

        out.append(self.widget_tree.get_object("docname"))

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        doc_txt = ""
        try:
            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
            doc_txt = self.core.call_success("i18n_date_short", doc_date)
        except Exception as exc:
            LOGGER.warning(
                "Failed to parse document date: %s --> %s", doc_id, exc
            )
        self.widget_tree.get_object("docname_entry").set_text(doc_txt)

    def _on_doc_date_changed(self, gtk_entry):
        txt = gtk_entry.get_text()
        r = self.core.call_success("i18n_parse_date_short", txt)
        if r is not None:
            self.core.call_all("gtk_entry_reset_colors", gtk_entry)
        else:
            self.core.call_all("gtk_entry_set_colors", gtk_entry, bg="#ee9000")

    def doc_properties_components_apply_changes(self, out):
        if out.multiple_docs:
            return

        doc_id = self.widget_tree.get_object("docname_entry").get_text()
        doc_date = self.core.call_success("i18n_parse_date_short", doc_id)
        if doc_date is None:
            LOGGER.warning(
                "Failed to parse document date: %s. Using as is", doc_id
            )
        else:
            doc_id = self.core.call_success("doc_get_id_by_date", doc_date)

        orig_id = out.doc_id
        orig_date = self.core.call_success("doc_get_date_by_id", orig_id)
        orig_date = orig_date.date()

        dest_id = doc_id
        dest_date = self.core.call_success("doc_get_date_by_id", dest_id)
        dest_date = dest_date.date()

        if orig_date == dest_date:
            return

        LOGGER.info("Previous document id: %s (%s)", orig_id, orig_date)
        LOGGER.info("New document id: %s (%s)", dest_id, dest_date)

        orig_url = self.core.call_success("doc_id_to_url", orig_id)
        dest_url = self.core.call_success(
            "doc_id_to_url", dest_id, existing=False
        )

        LOGGER.info("Renaming document %s into %s", orig_id, dest_id)
        dest_url = self.core.call_success(
            "doc_rename_by_url", orig_url, dest_url
        )
        dest_id = self.core.call_success("doc_url_to_id", dest_url)

        out.del_docs.add(out.doc_id)
        out.new_docs.add(dest_id)
        out.doc_id = dest_id

    def doc_properties_components_cancel_changes(self):
        self.doc_properties_components_set_active_doc(*self.active_doc)
