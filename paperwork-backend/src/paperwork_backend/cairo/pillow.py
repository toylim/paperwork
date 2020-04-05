import io
import logging

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise


CAIRO_AVAILABLE = False
GDK_AVAILABLE = False

DELAY_SHORT = 0.01
DELAY_LONG = 0.3

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import Gdk
        from gi.repository import GdkPixbuf
        GDK_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        from gi.repository import GLib
        from gi.repository import GObject
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        # dummy so chkdeps can still be called
        class GObject(object):
            class GObject(object):
                pass


LOGGER = logging.getLogger(__name__)


class ImgSurface(object):
    # wrapper so it can be weakref
    def __init__(self, surface):
        self.surface = surface


def pillow_to_surface(core, img, intermediate="pixbuf", quality=90):
    """
    Convert a PIL image into a Cairo surface
    """
    # TODO(Jflesch): Python 3 problem
    # cairo.ImageSurface.create_for_data() raises NotImplementedYet ...

    # img.putalpha(256)
    # (width, height) = img.size
    # imgd = img.tobytes('raw', 'BGRA')
    # imga = array.array('B', imgd)
    # stride = width * 4
    #  return cairo.ImageSurface.create_for_data(
    #      imga, cairo.FORMAT_ARGB32, width, height, stride)

    # So we fall back to those methods:

    if intermediate == "pixbuf" and (
                not hasattr(GdkPixbuf.Pixbuf, 'new_from_bytes') or
                img.getbands() != ('R', 'G', 'B')
            ):
        intermediate = "png"

    if intermediate == "pixbuf":

        data = GLib.Bytes.new(img.tobytes())
        (width, height) = img.size

        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            data, GdkPixbuf.Colorspace.RGB, False, 8,
            width, height, width * 3
        )
        img_surface = ImgSurface(cairo.ImageSurface(
            cairo.FORMAT_RGB24, width, height
        ))
        ctx = cairo.Context(img_surface.surface)
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0.0, 0.0)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()

    elif intermediate == "jpeg":

        if not hasattr(cairo.ImageSurface, 'set_mime_data'):
            LOGGER.warning(
                "Cairo %s does not support yet 'set_mime_data'."
                " Cannot include image as JPEG in the PDF."
                " Image will be included as PNG (much bigger)",
                cairo.version
            )
            intermediate = 'png'
        else:
            # IMPORTANT: The actual surface will be empty.
            # but mime-data will have attached the correct data
            # to the surface that supports it
            img_surface = ImgSurface(cairo.ImageSurface(
                cairo.FORMAT_RGB24, img.size[0], img.size[1]
            ))
            img_io = io.BytesIO()
            img.save(img_io, format="JPEG", quality=quality)
            img_io.seek(0)
            data = img_io.read()
            img_surface.surface.set_mime_data(cairo.MIME_TYPE_JPEG, data)

    if intermediate == "png":

        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        img_surface = ImgSurface(cairo.ImageSurface.create_from_png(img_io))

    if img_surface is None:
        raise Exception(
            "image2surface(): unknown intermediate: {}".format(intermediate)
        )

    core.call_all("on_objref_track", img_surface)
    return img_surface


class CairoRenderer(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    DEFAULT_BACKGROUND = (0.5, 0.5, 0.5)

    def __init__(self, core, work_queue_name, file_url):
        super().__init__()
        self.core = core
        self.work_queue_name = work_queue_name
        self.file_url = file_url
        self.size = (0, 0)
        self.zoom = 1.0
        self.cairo_surface = None
        self.background = self.DEFAULT_BACKGROUND
        self.visible = False

        # very often, the image is much bigger than what we actually display
        # --> keep a copy of the reduced image in memory
        self.cache = (-1.0, None)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.emit, args=("getting_size",)
        )
        promise = promise.then(
            core.call_success("url_to_img_size_promise", file_url)
        )
        promise = promise.then(self._set_img_size)
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.DelayPromise(
            core, DELAY_SHORT
        ))
        self.get_size_promise = promise
        self.getting_size = False

        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        # Give also time so the loading can be cancelled
        promise = openpaperwork_core.promise.DelayPromise(
            core, DELAY_LONG
        )
        promise = promise.then(core.call_success(
            "url_to_cairo_surface_promise", file_url
        ))
        promise = promise.then(self._set_cairo_surface)
        self.render_img_promise = promise
        self.render_job_in_queue = False

    def start(self):
        if self.getting_size:
            # seems render() may be called before start() in some cases
            # --> avoid calling twice work_queue_add_promise() to get the size
            return
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.get_size_promise
        )
        self.getting_size = True

    def render(self, force=False):
        if self.visible and not force:
            return
        self.visible = True
        if self.size == (0, 0):
            self.core.call_all(
                "work_queue_cancel", self.work_queue_name,
                self.get_size_promise
            )
            # re add with a higher priority
            self.core.call_success(
                "work_queue_add_promise",
                self.work_queue_name, self.get_size_promise,
                priority=200
            )
            self.getting_size = True
            return
        if self.render_job_in_queue:
            return
        self.render_job_in_queue = True
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.render_img_promise, priority=100
        )

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        if self.size == (0, 0):
            self.core.call_all(
                "work_queue_cancel", self.work_queue_name,
                self.get_size_promise
            )
            # re add with a lower priority
            self.core.call_success(
                "work_queue_add_promise",
                self.work_queue_name, self.get_size_promise
            )
            self.getting_size = True
        if self.cairo_surface is not None:
            self.cairo_surface.surface.finish()
            self.cairo_surface = None
            self.cache = (-1.0, None)
        self.render_job_in_queue = False
        self.core.call_all(
            "work_queue_cancel", self.work_queue_name, self.render_img_promise
        )

    def close(self):
        self.hide()
        self.core.call_all(
            "work_queue_cancel", self.work_queue_name, self.get_size_promise
        )
        self.get_size_promise = None
        self.getting_size = False
        self.render_img_promise = None

    def _set_img_size(self, size):
        self.size = size
        self.getting_size = False
        if self.get_size_promise is None:
            # Document has been closed while we looked for its size
            return
        self.emit("size_obtained")
        if self.visible:
            self.render(force=True)

    def _set_cairo_surface(self, surface):
        self.render_job_in_queue = False
        if not self.visible:  # visibility has changed
            surface.surface.finish()
            return
        self.cairo_surface = surface
        self.cache = (-1.0, None)
        self.emit("img_obtained")

    def _upd_cache(self):
        (cache_zoom, cache_img) = self.cache
        if cache_zoom == self.zoom:
            return

        img = ImgSurface(cairo.ImageSurface(
            cairo.FORMAT_RGB24,
            int(self.size[0] * self.zoom),
            int(self.size[1] * self.zoom),
        ))
        cairo_ctx = cairo.Context(img.surface)
        cairo_ctx.scale(self.zoom, self.zoom)
        cairo_ctx.set_source_surface(self.cairo_surface.surface)
        cairo_ctx.paint()

        self.cache = (self.zoom, img)

    def draw(self, cairo_ctx):
        if self.cairo_surface is None:
            cairo_ctx.save()
            try:
                size = self.size
                (r, g, b) = self.background
                cairo_ctx.set_source_rgb(r, g, b)
                cairo_ctx.rectangle(0, 0, size[0], size[1])
                cairo_ctx.clip()
                cairo_ctx.paint()
            finally:
                cairo_ctx.restore()
        else:
            self._upd_cache()
            cairo_ctx.save()
            try:
                cairo_ctx.set_source_surface(self.cache[1].surface)
                cairo_ctx.paint()
            finally:
                cairo_ctx.restore()


if GLIB_AVAILABLE:
    GObject.type_register(CairoRenderer)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'cairo_url',
            'pillow_to_surface',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'pillow',
                'defaults': ['paperwork_backend.pillow.img'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GDK_AVAILABLE:
            out['gdk'].update(openpaperwork_core.deps.GDK)
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def pillow_to_surface(self, pillow, intermediate="pixbuf", quality=90):
        return pillow_to_surface(self.core, pillow, intermediate, quality)

    def url_to_cairo_surface_promise(self, file_url):
        promise = self.core.call_success("url_to_pillow_promise", file_url)
        promise = promise.then(self.pillow_to_surface)
        return promise

    def url_to_cairo_surface(self, file_url):
        pil_img = self.core.call_success("url_to_pillow", file_url)
        return self.pillow_to_surface(pil_img)

    def cairo_renderer_by_url(self, work_queue_name, file_url):
        return CairoRenderer(self.core, work_queue_name, file_url)
