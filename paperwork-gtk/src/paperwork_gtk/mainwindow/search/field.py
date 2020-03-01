import logging

import openpaperwork_core
import openpaperwork_core.promise
import paperwork_backend.sync

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000000

    def __init__(self):
        super().__init__()
        self.search_entry = None
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'gtk_search_field',
            'syncable',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'index',
                'defaults': ['paperwork_backend.index.whoosh'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.search", "field.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.search_entry = self.widget_tree.get_object("search_entry")
        search_field = self.widget_tree.get_object("search_field")

        self.core.call_all("doclist_add", search_field, vposition=0)

        self.search_entry.connect(
            "search-changed", self.search_update_document_list
        )
        self.search_entry.connect("stop-search", lambda w: self.search_stop())

        self.core.call_all("work_queue_create", "doc_search")
        self.core.call_one(
            "mainloop_schedule", self.search_update_document_list
        )

    def search_update_document_list(self, _=None):
        self.core.call_all("work_queue_cancel_all", "doc_search")

        query = self.search_entry.get_text()
        LOGGER.info("Looking for [%s]", query)
        self.core.call_all("search_by_keywords", query)

    def search_by_keywords(self, query):
        self.core.call_all("on_search_start", query)
        if query == "":
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    "storage_get_all_docs", out
                )
            )
            promise = promise.then(
                lambda *args, **kwargs: [doc_id for (doc_id, doc_url) in out]
            )
        else:
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    "index_search", out, query
                )
            )
            promise = promise.then(lambda *args, **kwargs: out)
        promise = promise.then(lambda doc_ids: sorted(doc_ids, reverse=True))

        def show_if_query_still_valid(doc_ids):
            # While we were looking for the documents, the query may have
            # changed (user tying). No point in displaying obsolete results.
            if query != self.search_entry.get_text():
                return
            self.core.call_all("on_search_results", query, doc_ids)

        promise = promise.then(show_if_query_still_valid)

        self.core.call_all("work_queue_add_promise", "doc_search", promise)

    def search_stop(self):
        self.core.call_all("work_queue_cancel_all", "doc_search")

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                self.core.call_one(
                    "mainloop_schedule", self.search_update_document_list
                )

        out.append(RefreshTransaction(self.core, total_expected))

    def sync(self, promises: list):
        # If someone requested a sync, assume something has changed
        # --> try to keep the view as up-to-date as possible.
        self.search_update_document_list()

        promises.append(openpaperwork_core.promise.Promise(
            self.core, self.search_update_document_list
        ))
