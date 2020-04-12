import logging

try:
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class PageHoverHandler(object):
    def __init__(self, core, page):
        self.core = core
        self.page = page
        self.boxes = None
        self.actives = []

        self.realize_handler_id = None
        self.motion_handler_id = None

    def set_boxes(self, boxes, spatial_index):
        self.boxes = spatial_index

    def connect(self):
        assert(self.realize_handler_id is None)
        assert(self.motion_handler_id is None)
        self.realize_handler_id = self.page.widget.connect(
            "realize", self.on_realize
        )
        self.motion_handler_id = self.page.widget.connect(
            "motion-notify-event", self.on_motion
        )
        self.on_realize()

    def disconnect(self):
        assert(self.realize_handler_id is not None)
        assert(self.motion_handler_id is not None)
        self.page.widget.disconnect(self.realize_handler_id)
        self.page.widget.disconnect(self.motion_handler_id)
        self.realize_handler_id = None
        self.motion_handler_id = None

    def on_realize(self, widget=None):
        mask = Gdk.EventMask.POINTER_MOTION_MASK
        self.page.widget.add_events(mask)
        if self.page.widget.get_window() is not None:
            self.page.widget.get_window().set_events(
                self.page.widget.get_window().get_events() | mask
            )

    def on_motion(self, widget, event):
        if self.boxes is None:
            self.actives = []
            return
        zoom = self.page.get_zoom()
        x = int(event.x / zoom)
        y = int(event.y / zoom)
        actives = [(a[0], a[1].box) for a in self.boxes.get_boxes(x, y)]

        if len(actives) > 1:
            # will sort smaller areas last
            actives = [
                (abs((p[1][0] - p[0][0]) * (p[1][1] - p[0][1])), b)
                for (p, b) in actives
            ]
            actives.sort(reverse=True)

        actives = [
            a[1] for a in actives
        ]

        if actives != self.actives:
            self.page.widget.queue_draw()
        self.actives = actives

    def draw(self, cairo_ctx):
        for box in self.actives:
            self.core.call_all(
                "page_draw_box",
                cairo_ctx, self.page,
                box.position, (0.0, 0.0, 1.0),
                border_width=2, box_content=box.content
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

    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        h = PageHoverHandler(self.core, page)
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
