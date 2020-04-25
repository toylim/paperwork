import openpaperwork_core
import paperwork_backend.sync


DOC_ID = "help_intro"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100000  # see storage_get_all_docs()

    def __init__(self):
        super().__init__()
        self.doc_url = None
        self.thumbnail_url = None
        self.opened = False
        self.deleted = False

    def get_interfaces(self):
        return [
            'doc_labels',
            'document_storage',
            'syncable',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'help_documents',
                'defaults': ['paperwork_gtk.model.help'],
            },
        ]

    def init(self, core):
        super().init(core)

    def storage_get_all_docs(self, out: list):
        if self.deleted or len(out) > 0:
            self.doc_url = None
            return

        self.doc_url = self.core.call_success("doc_id_to_url", DOC_ID)
        out.append((DOC_ID, self.doc_url))

        if not self.opened:
            self.opened = True
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "doc_open", DOC_ID, self.doc_url
            )
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "docview_set_layout", "paged"
            )
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "doc_goto_page", 0
            )

    def labels_get_all(self, out: set):
        if self.doc_url is not None:
            self.core.call_all("help_labels_get_all", out)

    def storage_delete_doc_id(self, doc_id):
        if doc_id != DOC_ID:
            return
        self.doc_url = None
        self.deleted = True

    def _fake_delete_doc(self):
        if self.doc_url is None:
            return

        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs)
        all_docs = [doc for doc in all_docs if doc[0] != DOC_ID]

        if len(all_docs) <= 0:
            return

        self.deleted = True
        # make sure the index is up-to-date
        self.core.call_success(
            "transaction_simple", (("del", DOC_ID),)
        )

    def doc_transaction_start(self, out: list, total_expected=-1):
        class FakeDeleteDocTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                if self.doc_url is None:
                    return
                self._fake_delete_doc()

        out.append(FakeDeleteDocTransaction(self.core, total_expected))

    def sync(self, promises: list):
        if self.doc_url is None:
            return
        promises.append(openpaperwork_core.promise.Promise(
            self.core, self._fake_delete_doc
        ))
