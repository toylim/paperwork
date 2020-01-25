import datetime
import logging
import time

import openpaperwork_core
import openpaperwork_core.deps


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
        self.scrollbar = None
        self._scrollbar_last_value = -1
        self.doc_ids = []
        self.doc_visibles = 0
        self.last_date = datetime.datetime(year=1, month=1, day=1)
        self.row_to_docid = {}
        self.docid_to_row = {}
        self.active_docid = None

    def get_interfaces(self):
        return [
            'gtk_app_menu',
            'gtk_doclist',
            'search_listener',
        ]

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
                'interface': 'gtk_widget_flowlayout',
                'defaults': ['paprwork_gtk.widget.flowlayout'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.doclist", "doclist.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", "doclist.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.doclist = self.widget_tree.get_object("doclist_listbox")
        self.core.call_all(
            "mainwindow_add", side="left", name="doclist", prio=10000,
            header=self.widget_tree.get_object("doclist_header"),
            body=self.widget_tree.get_object("doclist_body"),
        )

        self.vadj = self.widget_tree.get_object(
            "doclist_scroll"
        ).get_vadjustment()
        self.vadj.connect("value-changed", self._on_scrollbar_value_changed)

        self.doclist.connect("row-activated", self._on_row_activated)

        self.menu_model = self.widget_tree.get_object("doclist_menu_model")

    def doclist_add(self, widget, vposition):
        body = self.widget_tree.get_object("doclist_body")
        body.add(widget)
        body.reorder_child(widget, vposition)

    def _doclist_clear(self):
        start = time.time()

        for child in self.doclist.get_children():
            self.doclist.remove(child)

        stop = time.time()

        LOGGER.info(
            "%d documents cleared in %dms",
            self.doc_visibles, (stop - start) * 1000
        )

    def doclist_clear(self):
        self._doclist_clear()
        self.last_date = datetime.datetime(year=1, month=1, day=1)
        self.doc_visibles = 0
        self.row_to_docid = {}
        self.docid_to_row = {}

    def doclist_refresh(self):
        self._doclist_clear()
        self.last_date = datetime.datetime(year=1, month=1, day=1)
        currently_visible = self.doc_visibles
        self.doc_visibles = 0
        self.doclist_extend(currently_visible)

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

        flowlayout = self.core.call_success(
            "gtk_widget_flowlayout_new", spacing=(3, 3)
        )
        flowlayout.set_visible(True)
        doc_box.pack_start(flowlayout, expand=True, fill=True, padding=0)
        doc_box.reorder_child(flowlayout, 1)

        self.core.call_all(
            "on_doc_box_creation", doc_id, widget_tree, flowlayout
        )

        row = widget_tree.get_object("doc_listbox")
        self.row_to_docid[row] = doc_id
        self.docid_to_row[doc_id] = row
        self.doclist.insert(row, -1)

    def doclist_extend(self, nb_docs):
        start = time.time()

        doc_ids = self.doc_ids[
            self.doc_visibles:self.doc_visibles + nb_docs
        ]
        LOGGER.info(
            "Adding %d documents to the document list (%d-%d)",
            len(doc_ids), self.doc_visibles, self.doc_visibles + nb_docs
        )

        for doc_id in doc_ids:
            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)

            if doc_date.year != self.last_date.year:
                doc_year = self.core.call_success(
                    "i18n_date_long_year", doc_date
                )
                self._add_date_box("year_box.glade", doc_year)

            if (doc_date.year != self.last_date.year or
                    doc_date.month != self.last_date.month):
                doc_month = self.core.call_success(
                    "i18n_date_long_month", doc_date
                )
                self._add_date_box("month_box.glade", doc_month)

            self.last_date = doc_date

            self._add_doc_box(doc_id)

        self.doc_visibles = min(
            len(self.doc_ids),
            self.doc_visibles + nb_docs
        )

        stop = time.time()

        LOGGER.info(
            "%d documents shown in %dms (%d displayable)",
            len(doc_ids), (stop - start) * 1000, len(self.doc_ids)
        )

        return len(doc_ids)

    def doclist_show(self, docs):
        self.doclist_clear()
        self.doc_ids = docs
        self.doclist_extend(NB_DOCS_PER_PAGE)

    def on_search_start(self, query):
        spinner = self.widget_tree.get_object("doclist_spinner")
        spinner.set_visible(True)
        spinner.start()

    def on_search_results(self, docs):
        self.doclist_show(docs)
        spinner = self.widget_tree.get_object("doclist_spinner")
        spinner.set_visible(False)
        spinner.stop()
        self._reselect_current_doc()

    def doc_close(self):
        self.active_docid = None

    def doc_open(self, doc_id, doc_url):
        self.active_docid = doc_id

    def _reselect_current_doc(self):
        if self.active_docid not in self.doc_ids:
            LOGGER.info(
                "Document %s not found in the document list",
                self.active_docid
            )
            self.vadj.set_value(self.vadj.get_lower())
            return

        row = self.docid_to_row.get(self.active_docid)
        while row is None:
            if self.doclist_extend(NB_DOCS_PER_PAGE) <= 0:
                break
            row = self.docid_to_row.get(self.active_docid)

        assert(row is not None)
        self.doclist.select_row(row)

        handler_id = None

        def scroll_to_row(row, allocation):
            adj = allocation.y
            adj -= self.vadj.get_page_size() / 2
            adj += allocation.height / 2
            min_val = self.vadj.get_lower()
            if adj < min_val:
                adj = min_val
            self.vadj.set_value(adj)
            row.disconnect(handler_id)

        handler_id = row.connect("size-allocate", scroll_to_row)

    def _on_scrollbar_value_changed(self, vadj):
        lower = vadj.get_lower()
        upper = vadj.get_upper() - lower
        value = (
            vadj.get_value() +
            vadj.get_page_size() -
            lower
        ) / upper

        if value < 0.95:
            return

        if self._scrollbar_last_value == vadj.get_value():
            # Previous extend call hasn't been taken into account yet
            return

        self.doclist_extend(NB_DOCS_PER_PAGE)
        self._scrollbar_last_value = vadj.get_value()

    def _on_row_activated(self, list_box, row):
        doc_id = self.row_to_docid[row]
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        LOGGER.info("Opening document %s (%s)", doc_id, doc_url)
        self.core.call_all("doc_open", doc_id, doc_url)

    def menu_app_append_item(self, item):
        # they are actually the same menu
        self.doclist_menu_append_item(item)

    def doclist_menu_append_item(self, item):
        self.menu_model.append_item(item)
