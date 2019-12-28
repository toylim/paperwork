import datetime
import logging
import time

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

# GtkListBox doesn't scale well with too many elements
# --> by default we only display 50 documents, and only extend the list
# as needed
NB_DOCS_PER_PAGE = 50


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.doclist = None
        self.doc_ids = []
        self.doc_visibles = 0

    def get_interfaces(self):
        return ['gtk_doclist']

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_widget_flowbox',
                'defaults': ['paprwork_gtk.widget.flowbox'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", "doclist.glade"
        )
        self.doclist = self.widget_tree.get_object("doclist_listbox")
        self.core.call_all(
            "mainwindow_add", side="left",
            name="doclist", prio=10000,
            header=self.widget_tree.get_object("doclist_header"),
            body=self.widget_tree.get_object("doclist_body"),
        )

    def doclist_add(self, widget, vposition):
        body = self.widget_tree.get_object("doclist_body")
        body.add(widget)
        body.reorder_child(widget, vposition)

    def doclist_clear(self):
        start = time.time()

        self.doclist.freeze_notify()
        self.doclist.freeze_child_notify()
        try:
            for child in self.doclist.get_children():
                self.doclist.remove(child)
        finally:
            self.doclist.thaw_child_notify()
            self.doclist.thaw_notify()

        stop = time.time()

        LOGGER.info(
            "%d documents cleared in %dms",
            self.doc_visibles, (stop - start) * 1000
        )
        self.doc_visibles = 0

    def _add_date_box(self, name, txt):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", name
        )
        widget_tree.get_object("date_label").set_text(txt)
        row = widget_tree.get_object("date_box")
        self.doclist.insert(row, -1)

    def _add_doc_box(self, doc_id):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", "doc_box.glade"
        )

        doc_box = widget_tree.get_object("doc_box")

        flowbox = self.core.call_success(
            "gtk_widget_flowbox_new", spacing=(3, 3)
        )
        flowbox.set_visible(True)
        doc_box.pack_start(flowbox, expand=True, fill=True, padding=0)
        doc_box.reorder_child(flowbox, 1)

        self.core.call_all("on_doc_box_creation", doc_id, widget_tree, flowbox)

        row = widget_tree.get_object("doc_listbox")
        self.doclist.insert(row, -1)

    def doclist_extend(self, nb_docs):
        last_date = datetime.datetime(year=1, month=1, day=1)

        start = time.time()

        doc_ids = self.doc_ids[
            self.doc_visibles:self.doc_visibles + nb_docs
        ]

        self.doclist.freeze_notify()
        self.doclist.freeze_child_notify()
        try:
            for doc_id in doc_ids:
                doc_date = self.core.call_success("doc_get_date_by_id", doc_id)

                if doc_date.year != last_date.year:
                    doc_year = self.core.call_success(
                        "i18n_date_long_year", doc_date
                    )
                    self._add_date_box("year_box.glade", doc_year)

                if (doc_date.year != last_date.year or
                        doc_date.month != last_date.month):
                    doc_month = self.core.call_success(
                        "i18n_date_long_month", doc_date
                    )
                    self._add_date_box("month_box.glade", doc_month)

                last_date = doc_date

                self._add_doc_box(doc_id)
        finally:
            self.doclist.thaw_child_notify()
            self.doclist.thaw_notify()

        self.doc_visibles = max(
            len(self.doc_ids),
            self.doc_visibles + nb_docs
        )

        stop = time.time()

        LOGGER.info(
            "%d documents shown in %dms (%d displayable)",
            len(doc_ids), (stop - start) * 1000, len(self.doc_ids)
        )

    def doclist_show(self, docs):
        self.doclist_clear()
        self.doc_ids = docs
        self.doclist_extend(NB_DOCS_PER_PAGE)
