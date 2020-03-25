import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class DocPropertiesUpdate(object):
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.modified = False


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
            "clicked", self._close_doc_properties
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
            self.widget_tree.get_object("docproperties_body").pack_start(
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

    def _close_doc_properties(self, *args, **kwargs):
        upd = DocPropertiesUpdate(self.active_doc[0])
        self.core.call_all("doc_properties_components_apply_changes", upd)

        if upd.modified or upd.doc_id != self.active_doc[0]:
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, self._upd_index, args=(self.active_doc[0], upd,),
            )
            promise.schedule()

        self.core.call_all(
            "mainwindow_show", side="left", name="doclist"
        )

    def _upd_index(self, doc_id, upd):
        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)

        if doc_id == upd.doc_id:
            # doc id hasn't changed --> it's just an update
            for transaction in transactions:
                transaction.upd_obj(upd.doc_id)
        else:
            # doc id changed
            for transaction in transactions:
                transaction.del_obj(doc_id)
            for transaction in transactions:
                transaction.add_obj(upd.doc_id)

        for transaction in transactions:
            transaction.commit()
