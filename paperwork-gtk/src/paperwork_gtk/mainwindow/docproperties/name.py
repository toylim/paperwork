import datetime
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

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
                'interface': 'gtk_doc_properties',
                'defaults': ['paperwork_gtk.docproperties'],
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

    def doc_properties_components_get(self, out: list):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "name.glade"
        )

        self.widget_tree.get_object("calendar_popover").set_relative_to(
            self.widget_tree.get_object("docname_entry")
        )
        self.widget_tree.get_object("docname_entry").connect(
            "icon-release", self._open_calendar
        )
        self.widget_tree.get_object("calendar_calendar").connect(
            "day-selected-double-click", self._update_date
        )

        out.append(self.widget_tree.get_object("docname"))

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        doc_txt = ""
        try:
            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
            self.widget_tree.get_object("calendar_calendar").select_month(
                doc_date.month - 1, doc_date.year
            )
            self.widget_tree.get_object("calendar_calendar").select_day(
                doc_date.day
            )
            doc_txt = self.core.call_success("i18n_date_short", doc_date)
        except Exception as exc:
            LOGGER.warning(
                "Failed to parse document date: %s --> %s", doc_id, exc
            )
        self.widget_tree.get_object("docname_entry").set_text(doc_txt)

    def _open_calendar(self, gtk_entry, icon_pos, event):
        self.widget_tree.get_object("calendar_popover").set_visible(True)

    def _update_date(self, gtk_calendar):
        date = self.widget_tree.get_object("calendar_calendar").get_date()
        date = datetime.datetime(year=date[0], month=date[1] + 1, day=date[2])
        date = self.core.call_success("i18n_date_short", date)
        self.widget_tree.get_object("docname_entry").set_text(date)
        self.widget_tree.get_object("calendar_popover").set_visible(False)

    def doc_properties_components_apply_changes(self, out):
        doc_id = self.widget_tree.get_object("docname_entry").get_text()
        try:
            doc_id = self.core.call_success("i18n_parse_date_short", doc_id)
            doc_id = self.core.call_success("doc_get_id_by_date", doc_id)
        except ValueError as exc:
            LOGGER.warning(
                "Failed to parse document date: %s. Using as is",
                exc_info=exc
            )

        orig_id = out.doc_id
        dest_id = doc_id

        if orig_id == dest_id:
            return

        LOGGER.info("Previous document id: %s", orig_id)
        LOGGER.info("New document id: %s", dest_id)

        orig_url = self.core.call_success("doc_id_to_url", orig_id)
        dest_url = self.core.call_success("doc_id_to_url", dest_id)

        LOGGER.info("Renaming document %s into %s", orig_id, dest_id)
        self.core.call_all("doc_rename_by_url", orig_url, dest_url)

        out.doc_id = dest_id
