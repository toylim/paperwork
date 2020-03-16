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
    def __init__(self, core, page):
        self.core = core
        self.page = page
        self.line_boxes = None
        self.word_boxes = None
        self.actives = []

        self.orig = (-1, -1)
        self.first = None

        self.gesture = Gtk.GestureDrag.new(page.widget)
        self.gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        self.signal_handlers = []

    def set_boxes(self, boxes):
        self.line_boxes = boxes
        self.word_boxes = []
        for line in boxes:
            self.word_boxes += line.word_boxes

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

    def _get_boxes(self, x, y):
        if self.boxes is None:
            return set()
        x += self.orig[0]
        y += self.orig[1]
        zoom = self.page.get_zoom()
        pos = (int(x / zoom), int(y / zoom))
        return set(self.boxes.intersection(pos, objects=True))

    def _find_closest(self, x, y):
        if self.word_boxes is None:
            return
        zoom = self.page.get_zoom()
        x /= zoom
        y /= zoom
        return min({
            (
                # distance squared
                ((x - ((box.position[0][0] + box.position[1][0]) / 2)) ** 2) +
                ((y - ((box.position[0][1] + box.position[1][1]) / 2)) ** 2),
                box
            )
            for box in self.word_boxes
        })[1]

    def _get_selected(self, last):
        actives = None
        for line in self.line_boxes:
            for word in line.word_boxes:
                if word is self.first or word is last:
                    if actives is None:
                        actives = []
                    else:
                        return actives
                if actives is not None:
                    actives.append(word)
        return []

    def on_drag_begin(self, gesture, x, y):
        self.actives = []
        self.orig = (x, y)
        self.first = self._find_closest(x, y)

    def on_drag_update(self, gesture, x, y):
        (x, y) = (self.orig[0] + x, self.orig[1] + y)
        last = self._find_closest(x, y)
        actives = self._get_selected(last)
        if len(self.actives) != len(actives):
            self.page.widget.queue_draw()
        self.actives = actives
        LOGGER.info("%d selected boxes", len(self.actives))

    def on_drag_end(self, gesture, x, y):
        self.on_drag_update(gesture, x, y)
        self.core.call_all(
            "on_page_boxes_selected",
            self.page.doc_id, self.page.doc_url, self.page.page_idx,
            self.actives
        )

    def draw(self, cairo_ctx):
        for box in self.actives:
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

    def on_page_boxes_loaded(self, page, boxes):
        h = PageSelectionHandler(self.core, page)
        self.handlers[page.widget] = h

        assert(page.widget in self.handlers)
        h = self.handlers[page.widget]
        h.set_boxes(boxes)
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
