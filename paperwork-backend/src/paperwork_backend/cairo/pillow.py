import io
import logging
import time

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise


CAIRO_AVAILABLE = False
GDK_AVAILABLE = False

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
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


def pillow_to_surface(img, intermediate="pixbuf", quality=90):
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

    start = time.time()

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

    stop = time.time()

    LOGGER.info(
        "Took %dms to convert Pillow image to Cairo surface"
        " (size=%s, intermediate=%s)",
        (stop - start) * 1000, img.size, intermediate
    )
    return img_surface


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
        return pillow_to_surface(pillow, intermediate, quality)

    def url_to_cairo_surface_promise(self, file_url):
        promise = self.core.call_success("url_to_pillow_promise", file_url)
        promise = promise.then(self.pillow_to_surface)
        return promise
