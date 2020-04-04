import logging

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)
        self.updated = set()
        self.promise = None

    def get_interfaces(self):
        return [
            'doc_open',
            'gtk_drag_and_drop'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.promise = openpaperwork_core.promise.Promise(self.core)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _parse_paperwork_uri(self, uri):
        infos = uri.split("#", 1)[1]
        infos = infos.split("&")
        infos = (i.split("=", 1) for i in infos)
        infos = {k: v for (k, v) in infos}
        return (infos['doc_id'], int(infos['page']))

    def doc_close(self):
        self.active_doc = (None, None)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def drag_and_drop_page_enable(self, widget):
        """
        Arguments:
            widget - GTK widget on which page drag'n'drop must be enabled.

        When a drop is received, it will call the method
        'drag_and_drop_get_destination(widget, x, y)'.
        The plugin to whom the widget belongs should reply with
        (doc_id, page_idx).
        """
        widget.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE)
        targets = Gtk.TargetList.new([])
        targets.add_uri_targets(0)
        widget.drag_dest_set_target_list(targets)
        widget.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_received(
            self, widget, drag_context, x, y, selection_data, info, time):
        uris = selection_data.get_uris()
        LOGGER.info(
            "drag_data_received(%s, %d, %d, %s, %s)",
            widget, x, y, uris, info
        )

        dst = self.core.call_success(
            "drag_and_drop_get_destination", widget, x, y
        )
        if dst is None:
            LOGGER.error("Nobody accepted a drop on %s (%d, %d)", widget, x, y)
            return

        (dst_doc_id, dst_page_idx) = dst

        for uri in reversed(uris):
            LOGGER.info("Drop: URI: %s", uri)

            self.core.call_all(
                "drag_and_drop_page_add", uri, dst_doc_id, dst_page_idx
            )

        self.core.call_all("drag_and_drop_apply")

    def drag_and_drop_page_add(self, src_uri, dst_doc_id, dst_page_idx):
        LOGGER.info("Drop: %s --> %s p%d", src_uri, dst_doc_id, dst_page_idx)

        if "doc_id=" not in src_uri or "page=" not in src_uri:
            # treat it as an import
            # TODO(Jflesch)
            return
        else:
            # moving page inside the current document
            (src_doc_id, src_page_idx) = self._parse_paperwork_uri(src_uri)

        src_doc_url = self.core.call_success("doc_id_to_url", src_doc_id)

        if src_doc_id == dst_doc_id and src_page_idx < dst_page_idx:
            dst_page_idx -= 1
        dst_doc_url = self.core.call_success("doc_id_to_url", dst_doc_id)
        dst_page_idx = max(dst_page_idx, 0)

        LOGGER.info(
            "Drop: %s p%d --> %s p%d",
            src_doc_id, src_page_idx,
            dst_doc_id, dst_page_idx
        )

        if src_doc_id == dst_doc_id and src_page_idx == dst_page_idx:
            return

        self.promise = self.promise.then(
            self.core.call_all, "page_move_by_url",
            src_doc_url, src_page_idx,
            dst_doc_url, dst_page_idx
        )
        self.promise = self.promise.then(lambda *args, **kwargs: None)

        for (doc_id, page_idx) in (
                (src_doc_id, src_page_idx),
                (dst_doc_id, dst_page_idx)):
            if doc_id == self.active_doc[0]:
                self.promise = self.promise.then(
                    self.core.call_all, "doc_reload_page",
                    *self.active_doc, page_idx
                )
                self.promise = self.promise.then(lambda *args, **kwargs: None)

        self.updated.add(src_doc_id)
        self.updated.add(dst_doc_id)

    def drag_and_drop_apply(self):
        if len(self.updated) <= 0:
            LOGGER.info("Nothing to do")
            return

        transactions = []
        self.core.call_all(
            "doc_transaction_start", transactions, len(self.updated)
        )
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.promise = self.promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self._run_transactions,
                args=(transactions, self.updated)
            )
        )
        self.promise.schedule()

        self.updated = set()
        self.promise = openpaperwork_core.promise.Promise(self.core)

    def _run_transactions(self, transactions, updated_doc_ids):
        for doc_id in updated_doc_ids:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            upd = (self.core.call_success("is_doc", doc_url) is not None)
            for transaction in transactions:
                if upd:
                    transaction.upd_obj(doc_id)
                else:
                    # drag'n'dropping deletes a document when there are no
                    # pages left in it.
                    transaction.del_obj(doc_id)
        for transaction in transactions:
            transaction.commit()