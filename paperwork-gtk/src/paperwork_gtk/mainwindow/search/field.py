import logging

import openpaperwork_core
import openpaperwork_core.promise


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

    def search_update_document_list(self, _=None):
        query = self.search_entry.get_text()
        LOGGER.info("Looking for [%s]", query)

        out = []
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda: self.core.call_all(
                "index_search", out, query
            )
        )
        promise = promise.then(lambda _: out.sort(reverse=True))
        promise = promise.then(self.core.call_all, "doclist_show", out)
        promise.schedule()

    def search_stop(self):
        pass

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshDocListTransaction(object):
            def add_obj(s, doc_id):
                pass

            def upd_obj(s, doc_id):
                pass

            def del_obj(s, doc_id):
                pass

            def unchanged_obj(s, doc_id):
                pass

            def cancel(s):
                pass

            def commit(s):
                self.search_update_document_list()

        out.append(RefreshDocListTransaction())

    def sync(self, promises: list):
        promises.append(openpaperwork_core.promise.Promise(
            self.core, self.search_update_document_list
        ))
