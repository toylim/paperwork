import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

    # workaround so chkdeps can still be called
    class GObject(object):
        class GObject(object):
            pass


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext


class Scan(GObject.GObject):
    """
    Implements the same interface than the mainwindow.docview.pageview.Page
    objects, but display any scan relative to the current document.
    """

    __gsignals__ = {
        # never emitted
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),

        # emitted when a scan is started
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),

        # never emitted
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),

        'visibility_changed': (GObject.SignalFlags.RUN_LAST, None, (
            # TODO(Jflesch): not implemented here (never emitted), but not
            # used anywhere anyway.
            GObject.TYPE_BOOLEAN,
        )),
    }

    def __init__(self, core, flow_layout, doc_id, scan_id=None):
        super().__init__()
        self.core = core
        self.flow_layout = flow_layout
        self.doc_id = doc_id
        self.zoom = 1.0
        self.page_idx = -1

        self.scan_id = scan_id
        self.size = (0, 0)

        if scan_id is not None:
            scan_id = self.core.call_success(
                "draw_scan_get_max_size", self.scan_id
            )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.scanview", "scanview.glade"
        )
        self.widget = self.widget_tree.get_object("scanview_area")
        self.set_visible(False)

    def __str__(self):
        return "Scan renderer ({})".format(self.doc_id)

    def set_visible(self, visible):
        if visible:
            self.widget.set_visible(True)
            size = self.get_size()
            self.widget.set_size_request(size[0], size[1])
            self.core.call_all("draw_scan_start", self.widget, self.scan_id)
        else:
            self.widget.set_visible(False)
            self.core.call_all("draw_scan_stop", self.widget)

    def close(self):
        pass

    def get_zoom(self):
        return self.zoom

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.resize()

    def get_full_size(self):
        if self.scan_id is None:
            return (0, 0)
        return self.size

    def get_size(self):
        size = self.get_full_size()
        return (
            int(size[0] * self.zoom),
            int(size[1] * self.zoom)
        )

    def resize(self):
        if self.scan_id is None:
            return
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])

    def refresh(self, reload=False):
        self.widget.queue_draw()

    def hide(self):
        pass

    def show(self):
        pass


if GLIB_AVAILABLE:
    GObject.type_register(Scan)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000

    def __init__(self):
        super().__init__()
        self.scan = None
        self.doc_id = None

    def get_interfaces(self):
        return [
            'gtk_pageview',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_drawer_scan',
                'defaults': [
                    'paperwork_gtk_drawer.calibration',
                    'paperwork_gtk_drawer.scan',
                ],
            },
        ]

    def doc_open_components(self, pages, doc_id, doc_url, page_container):
        self.doc_id = doc_id
        scan_id = self.core.call_success("scan2doc_doc_id_to_scan_id", doc_id)
        self.scan = Scan(self.core, page_container, doc_id, scan_id)
        pages.append(self.scan)

    def on_scan2doc_start(self, scan_id, doc_id, doc_url):
        if self.scan is None:
            return
        if doc_id != self.doc_id:
            return
        self.scan.scan_id = scan_id

    def on_scan_feed_start(self, scan_id):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return
        self.scan.set_visible(True)

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return
        self.scan.size = (scan_params.get_width(), scan_params.get_height())
        self.scan.resize()

    def on_scan_feed_end(self, scan_id):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return
        self.scan.set_visible(False)

    def on_scan2doc_end(self, scan_id, doc_id, doc_url):
        if self.scan is None:
            return
        if doc_id != self.doc_id:
            return
        self.scan.scan_id = None
