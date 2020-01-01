import io
import logging
import time

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise


CAIRO_AVAILABLE = False
GDK_AVAILABLE = False

DELAY = 0.01


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
        from gi.repository import GObject
        from gi.repository import Gdk
        from gi.repository import GdkPixbuf
        GDK_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        from gi.repository import GLib
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


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

    core.call_all("on_perfcheck_start", "pillow_to_surface")

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
        img_surface = cairo.ImageSurface(
            cairo.FORMAT_RGB24, width, height
        )
        ctx = cairo.Context(img_surface)
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
            img_surface = cairo.ImageSurface(
                cairo.FORMAT_RGB24, img.size[0], img.size[1]
            )
            img_io = io.BytesIO()
            img.save(img_io, format="JPEG", quality=quality)
            img_io.seek(0)
            data = img_io.read()
            img_surface.set_mime_data(
                cairo.MIME_TYPE_JPEG, data
            )

    if intermediate == "png":

        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        img_surface = cairo.ImageSurface.create_from_png(img_io)

    if img_surface is None:
        raise Exception(
            "image2surface(): unknown intermediate: {}".format(intermediate)
        )

    core.call_all(
        "on_perfcheck_stop", "pillow_to_surface",
        size=img.size, intermediate=intermediate
    )
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
        self.size_factor = 1.0
        self.cairo_surface = None
        self.background = self.DEFAULT_BACKGROUND

        promise = core.call_success("url_to_img_size_promise", file_url)
        promise = promise.then(self._set_img_size)
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            core, time.sleep, args=(DELAY,)
        ))
        self.get_size_promise = promise

        promise = core.call_success(
            "url_to_cairo_surface_promise", file_url
        )
        promise = promise.then(self._set_cairo_surface)
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            core, time.sleep, args=(DELAY,)
        ))
        self.render_img_promise = promise

    def start(self):
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.get_size_promise
        )

    def render(self):
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.render_img_promise, priority=100
        )

    def hide(self):
        self.cairo_surface = None
        self.core.call_all(
            "work_queue_cancel", self.work_queue_name, self.render_img_promise
        )

    def _set_img_size(self, size):
        self.emit("getting_size")
        self.size = size
        self.emit("size_obtained")

    def _set_cairo_surface(self, surface):
        self.cairo_surface = surface
        self.emit("img_obtained")

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
            cairo_ctx.save()
            try:
                cairo_ctx.scale(self.size_factor, self.size_factor)
                cairo_ctx.set_source_surface(self.cairo_surface)
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

    def cairo_renderer_by_url(self, work_queue_name, file_url):
        return CairoRenderer(self.core, work_queue_name, file_url)
