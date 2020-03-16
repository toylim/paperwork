import logging

try:
    import gi
    gi.require_version('Pango', '1.0')
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import Pango
    from gi.repository import PangoCairo
    PANGO_AVAILABLE = True
except (ImportError, ValueError):
    PANGO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
DELAY = 0.01


class Plugin(openpaperwork_core.PluginBase):
    """
    Load the boxes on the pages and notify them to other plugins.
    Do nothing else. See other plugins in
    paperwork_gtk.mainwindow.docview.pageview.boxes to have something actually
    happening.
    """

    def __init__(self):
        super().__init__()
        self.cache = {}

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_pageview_boxes',
        ]

    def get_deps(self):
        return [
            {
                "interface": "gtk_pageview",
                "defaults": ["paperwork_gtk.mainwindow.docview.pageview"],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def chkdeps(self, out: dict):
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)

    def doc_close(self):
        self.cache = {}

    def doc_open(self, *args, **kwargs):
        self.doc_close()

    def _set_boxes(self, boxes, page):
        ref = (page.doc_id, page.page_idx)
        self.cache[ref] = boxes
        return boxes

    def pageview_get_boxes_by_id(self, doc_id, page_idx):
        ref = (doc_id, page_idx)
        if ref not in self.cache:
            return None
        return self.cache[ref]

    def on_page_visibility_changed(self, page, visible):
        if not visible:
            return

        ref = (page.doc_id, page.page_idx)
        if ref in self.cache:
            return

        # even they are not yet loaded, they will soon be --> we can mark them
        # as loaded
        self.cache[ref] = None

        promise = openpaperwork_core.promise.Promise(
            self.core, LOGGER.debug,
            args=("Loading boxes of %s p%d", page.doc_id, page.page_idx)
        )
        # drop the returned value
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_success,
            args=("page_get_boxes_by_url", page.doc_url, page.page_idx,)
        ))
        promise = promise.then(lambda boxes=[]: self._set_boxes(boxes, page))
        promise = promise.then(lambda boxes=[]: self.core.call_all(
            "on_page_boxes_loaded", page, boxes
        ))
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.DelayPromise(
            self.core, DELAY
        ))

        # Piggyback the work queue of pageview.
        self.core.call_success(
            "work_queue_add_promise", "page_loader", promise, priority=-10
        )

    def on_page_boxes_loaded(self, page, boxes):
        LOGGER.info(
            "Page %s %d: %d line boxes loaded",
            page.doc_id, page.page_idx, len(boxes)
        )

    def paint_txt(self, cairo_ctx, txt, x, y, w, h):
        cairo_ctx.set_source_rgb(1.0, 1.0, 1.0)
        cairo_ctx.rectangle(x, y, w, h)
        cairo_ctx.fill()

        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(txt, -1)
        txt_size = layout.get_size()
        if 0 in txt_size:
            return

        cairo_ctx.save()
        try:
            txt_factor = min(
                float(w) * Pango.SCALE / txt_size[0],
                float(h) * Pango.SCALE / txt_size[1],
            )
            cairo_ctx.set_source_rgb(0, 0, 0)
            cairo_ctx.translate(x, y)

            # make the text use the whole box space
            cairo_ctx.scale(txt_factor, txt_factor)

            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
        finally:
            cairo_ctx.restore()

    def page_draw_box(
            self, cairo_ctx, page, box_position,
            border_color, border_width=2,
            box_content=None):
        zoom = page.zoom
        ((tl_x, tl_y), (br_x, br_y)) = box_position
        tl_x *= zoom
        tl_y *= zoom
        br_x *= zoom
        br_y *= zoom
        w = br_x - tl_x
        h = br_y - tl_y

        if box_content is not None:
            self.paint_txt(cairo_ctx, box_content, tl_x, tl_y, w, h)

        cairo_ctx.save()
        try:

            cairo_ctx.set_source_rgb(
                border_color[0], border_color[1], border_color[2]
            )
            cairo_ctx.set_line_width(border_width)
            cairo_ctx.rectangle(
                tl_x - (border_width / 2),
                tl_y - (border_width / 2),
                w + border_width,
                h + border_width
            )
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()
