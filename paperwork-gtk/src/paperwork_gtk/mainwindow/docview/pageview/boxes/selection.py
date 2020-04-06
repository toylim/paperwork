import itertools
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
IDX_GENERATOR = itertools.count()


class PageSelectionHandler(object):
    def __init__(self, core, plugin, page):
        self.core = core
        self.plugin = plugin
        self.page = page

        self.actives = []
        self.boxes = None

        self.orig = (-1, -1)
        self.first = None
        self.last = None

        self.gesture = Gtk.GestureDrag.new(page.widget)
        self.gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        self.signal_handlers = []

    def set_boxes(self, line_boxes, spatial_index):
        self.boxes = spatial_index

    def connect(self):
        self.disconnect()
        handlers = (
            ('drag-begin', self.on_drag_begin),
            ('drag-update', self.on_drag_update),
            ('drag-end', self.on_drag_end),
        )
        for (signal, cb) in handlers:
            self.signal_handlers.append(
                (signal, self.gesture.connect(signal, cb))
            )

    def disconnect(self):
        for (signal, handler_id) in self.signal_handlers:
            self.gesture.disconnect(handler_id)
        self.signal_handlers = []

    def _find_box(self, x, y):
        if self.boxes is None:
            return None
        zoom = self.page.get_zoom()
        x /= zoom
        y /= zoom
        nboxes = self.boxes.get_boxes(x, y)

        # take the box with the smallest area
        try:
            nbox = min({
                (
                    abs(
                        (n[1].box.position[1][0] - n[1].box.position[0][0]) *
                        (n[1].box.position[1][1] - n[1].box.position[0][1])
                    ), n[1]
                )
                for n in nboxes
            })[1]
        except ValueError:
            return None
        return nbox

    def _get_selected(self):
        if self.first is None:
            return []

        if self.first.index <= self.last.index:
            first = self.first
            last = self.last
        else:
            first = self.last
            last = self.first

        current = first

        while current is not None and current != last:
            yield current.box
            current = current.next

        yield last.box

    def on_drag_begin(self, gesture, x, y):
        if not self.plugin.enabled:
            self.first = None
            self.last = None
            return

        self.actives = []
        self.orig = (x, y)
        self.first = self._find_box(x, y)
        self.last = self.first

    def on_drag_update(self, gesture, x, y):
        if self.first is None:
            return

        (x, y) = (self.orig[0] + x, self.orig[1] + y)
        last = self._find_box(x, y)

        if last is None or last == self.last:
            return

        self.last = last
        self.page.widget.queue_draw()

        LOGGER.info(
            "Text selection: first: %d ; last: %d",
            self.first.index, self.last.index
        )

    def on_drag_end(self, gesture, x, y):
        if self.first is None:
            return

        self.on_drag_update(gesture, x, y)
        self.core.call_all(
            "on_page_boxes_selected",
            self.page.doc_id, self.page.doc_url, self.page.page_idx,
            list(self._get_selected())
        )

    def draw(self, cairo_ctx):
        if not self.plugin.enabled:
            return

        for box in self._get_selected():
            self.core.call_all(
                "page_draw_box",
                cairo_ctx, self.page,
                box.position, (0.0, 1.0, 0.0),
                border_width=2
            )


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10

    def __init__(self):
        super().__init__()
        self.handlers = {}
        self.enabled = False

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_pageview_boxes_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_pageview',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageview'],
            },
            {
                'interface': 'gtk_pageview_boxes',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageview.boxes'
                ],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_docview_closed_page(self, page):
        self.handlers.pop(page.widget).disconnect()

    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        h = PageSelectionHandler(self.core, self, page)
        self.handlers[page.widget] = h

        assert(page.widget in self.handlers)
        h = self.handlers[page.widget]
        h.set_boxes(boxes, spatial_index)
        if page.get_visible():
            h.connect()

    def on_page_visibility_changed(self, page, visible):
        if page.widget not in self.handlers:
            return
        h = self.handlers[page.widget]
        if visible:
            h.connect()
        else:
            h.disconnect()

    def on_page_draw(self, cairo_ctx, page):
        if page.widget not in self.handlers:
            return
        self.handlers[page.widget].draw(cairo_ctx)

    def on_layout_change(self, layout_name):
        self.enabled = (layout_name == 'paged')
