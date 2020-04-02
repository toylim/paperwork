import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class DocPropertiesUpdate(object):
    def __init__(self, doc_id):
        self.doc_id = doc_id

        self.new_docs = set()
        self.upd_docs = set()
        self.del_docs = set()


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.active_doc = None

    def get_interfaces(self):
        return ['gtk_doc_properties']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.active_doc = None

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "docproperties.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("docproperties_back").connect(
            "clicked", self._apply
        )
        self.widget_tree.get_object("docproperties_cancel").connect(
            "clicked", self._cancel
        )

        self.core.call_all(
            "mainwindow_add", side="left", name="docproperties", prio=0,
            header=self.widget_tree.get_object("docproperties_header"),
            body=self.widget_tree.get_object("docproperties_body"),
        )

        self.core.call_one("mainloop_schedule", self._build_doc_properties)

    def _build_doc_properties(self):
        components = []
        self.core.call_all("doc_properties_components_get", components)
        for component in components:
            self.widget_tree.get_object("docproperties_box").pack_start(
                component, expand=False, fill=True, padding=0
            )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
        doc_txt = self.core.call_success("i18n_date_short", doc_date)
        self.widget_tree.get_object("docproperties_header").set_title(
            _("Properties of %s") % doc_txt
        )
        self.core.call_all(
            "doc_properties_components_set_active_doc", doc_id, doc_url
        )

    def open_doc_properties(self, doc_id, doc_url):
        self.core.call_all(
            "mainwindow_show", side="left", name="docproperties"
        )

    def _apply(self, *args, **kwargs):
        LOGGER.info("Changes validated by the user")
        upd = DocPropertiesUpdate(self.active_doc[0])

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("doc_properties_components_apply_changes", upd)
        )
        # drop call_all return value
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._reload_doc, upd)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._upd_index, args=(upd,),
        ))
        promise.schedule()

        self.core.call_all("mainwindow_show_default", side="left")

    def _cancel(self, *args, **kwargs):
        LOGGER.info("Changes cancelled by the user")
        self.core.call_all("doc_properties_components_cancel_changes")
        self.core.call_all(
            "mainwindow_show", side="left", name="doclist"
        )

    def _reload_doc(self, upd):
        if upd.doc_id == self.active_doc[0]:
            return
        doc_url = self.core.call_success("doc_id_to_url", upd.doc_id)
        LOGGER.info("Document renamed. Opening %s (%s)", upd.doc_id, doc_url)
        self.core.call_all("doc_close")
        self.core.call_all("doc_open", upd.doc_id, doc_url)

    def _upd_index(self, upd):
        total = len(upd.new_docs) + len(upd.upd_docs) + len(upd.del_docs)

        if total <= 0:
            LOGGER.info("Document %s not modified. Nothing to do", upd.doc_id)
            return

        LOGGER.info(
            "Document %s modified. %d documents impacted", upd.doc_id, total
        )

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, total)
        transactions.sort(key=lambda transaction: -transaction.priority)

        for doc_id in upd.new_docs:
            for transaction in transactions:
                transaction.add_obj(doc_id)
        for doc_id in upd.upd_docs:
            for transaction in transactions:
                transaction.upd_obj(doc_id)
        for doc_id in upd.del_docs:
            for transaction in transactions:
                transaction.del_obj(doc_id)

        for transaction in transactions:
            transaction.commit()
