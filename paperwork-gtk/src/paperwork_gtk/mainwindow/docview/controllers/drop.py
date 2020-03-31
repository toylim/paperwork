"""
When drag'n'dropping, enables the dropping-in-a-document part.
"""

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

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class DropController(BaseDocViewController):
    LINE_BORDERS = 10
    LINE_WIDTH = 3
    LINE_COLOR = (0.0, 0.8, 1.0, 1.0)

    def __init__(self, core, plugin):
        super().__init__(plugin)
        self.core = core
        self.closest = None
        self.target = None
        self.beforeafter = -1  # 0 for before the widget, 1 for after

    @staticmethod
    def _compute_squared_distance(rect, x, y):
        pts = (
            (rect.x, rect.y),
            (rect.x + rect.width, rect.y),
            (rect.x, rect.y + rect.height),
            (rect.x + rect.width, rect.y + rect.height),
        )
        dists = {
            ((abs(pt[0] - x) ** 2) + (abs(pt[1] - y) ** 2))
            for pt in pts
        }
        return min(dists)

    @staticmethod
    def _compute_beforeafter(rect, x, y):
        center = rect.x + (rect.width / 2)
        return 0 if x < center else 1

    def on_drag_motion(self, drag_context, x, y, time):
        super().on_drag_motion(drag_context, x, y, time)
        dists = {
            (
                self._compute_squared_distance(widget.get_allocation(), x, y),
                widget
            )
            for widget in self.plugin.page_layout.get_children()
        }
        try:
            self.closest = min(dists)[1]
        except ValueError:
            # empty list of widgets
            self.closest = None
            self.beforeafter = -1
            return

        self.beforeafter = self._compute_beforeafter(
            self.closest.get_allocation(), x, y
        )

        self.plugin.page_layout.queue_draw()

    def on_drag_leave(self, drag_context, time):
        super().on_drag_leave(drag_context, time)
        self.target = self.closest
        self.closest = None
        self.plugin.page_layout.queue_draw()

    def on_draw(self, cairo_ctx):
        super().on_draw(cairo_ctx)

        if self.closest is None:
            return

        allocation = self.closest.get_allocation()
        height = allocation.height
        x = allocation.x
        x -= 2 * self.LINE_BORDERS
        x += (self.beforeafter * (allocation.width + 2 * self.LINE_BORDERS))
        x = max(0, x)
        y = allocation.y

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(*self.LINE_COLOR)
            cairo_ctx.set_line_width(self.LINE_WIDTH)

            cairo_ctx.move_to(x + self.LINE_BORDERS, y)
            cairo_ctx.line_to(x + self.LINE_BORDERS, y + height)
            cairo_ctx.stroke()

            cairo_ctx.move_to(x, y + self.LINE_BORDERS)
            cairo_ctx.line_to(
                x + (2 * self.LINE_BORDERS),
                y + self.LINE_BORDERS
            )
            cairo_ctx.stroke()

            cairo_ctx.move_to(x, y + height - self.LINE_BORDERS)
            cairo_ctx.line_to(
                x + (2 * self.LINE_BORDERS),
                y + height - self.LINE_BORDERS
            )
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()

    def _parse_paperwork_uri(self, uri):
        infos = uri.split("#", 1)[1]
        infos = infos.split("&")
        infos = (i.split("=") for i in infos)
        infos = {k: v for (k, v) in infos}
        return (infos['doc_id'], int(infos['page']))

    def on_drag_data_received(
            self, drag_context, x, y, selection_data,
            info, time):
        super().on_drag_data_received(
            drag_context, x, y, selection_data, info, time
        )
        if self.target is None:
            # shouldn't happen
            LOGGER.warning("Drop received but no target ?")
            return

        LOGGER.info("Drop received")

        uris = selection_data.get_uris()

        updated = set()

        promise = openpaperwork_core.promise.Promise(self.core)

        for uri in uris:
            LOGGER.info("Drop: URI: %s", uri)

            if "doc_id=" not in uri or "page=" not in uri:
                # treat it as an import
                # TODO
                continue
            else:
                # moving page inside the current document
                (src_doc_id, src_page_idx) = self._parse_paperwork_uri(uri)

            src_doc_url = self.core.call_success("doc_id_to_url", src_doc_id)

            page = self.plugin.widget_to_page[self.target]

            dst_page_idx = page.page_idx + self.beforeafter
            if src_page_idx < dst_page_idx:
                dst_page_idx -= 1
            dst_page_idx = max(dst_page_idx, 0)

            LOGGER.info(
                "Drop: %s p%d --> %s p%d",
                src_doc_id, src_page_idx,
                self.plugin.active_doc[0], dst_page_idx
            )

            if src_page_idx == dst_page_idx:
                continue

            updated.add(src_doc_id)
            updated.add(self.plugin.active_doc[0])

            promise = promise.then(
                self.core.call_all, "page_move_by_url",
                src_doc_url, src_page_idx,
                self.plugin.active_doc[1], dst_page_idx
            )
            promise = promise.then(lambda *args, **kwargs: None)

        if len(updated) <= 0:
            LOGGER.info("Nothing to do")
            return

        if src_doc_id == self.plugin.active_doc[0]:
            promise = promise.then(
                self.core.call_all, "doc_reload_page",
                *self.plugin.active_doc, src_page_idx
            )
            promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, "doc_reload_page",
            *self.plugin.active_doc, dst_page_idx
        )
        promise = promise.then(lambda *args, **kwargs: None)

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, len(updated))
        transactions.sort(key=lambda transaction: -transaction.priority)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._run_transactions, args=(transactions, updated)
        ))
        promise.schedule()

    def _run_transactions(self, transactions, updated_doc_ids):
        for doc_id in updated_doc_ids:
            for transaction in transactions:
                transaction.upd_obj(doc_id)
        for transaction in transactions:
            transaction.commit()


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_docview_controller',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_docview_init(self, docview):
        docview.page_layout.drag_dest_set(
            Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE
        )

        targets = Gtk.TargetList.new([])
        targets.add_uri_targets(0)
        docview.page_layout.drag_dest_set_target_list(targets)

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['drop'] = DropController(self.core, docview)
