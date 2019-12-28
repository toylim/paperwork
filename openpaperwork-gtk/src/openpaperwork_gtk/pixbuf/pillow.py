import io
import logging

import openpaperwork_core

try:
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except (ValueError, ImportError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf
    GDK_PIXBUF_AVAILABLE = True
except (ValueError, ImportError):
    GDK_PIXBUF_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'pixbuf_pillow',
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['gi.repository.GLib']['debian'] = 'gir1.2-glib-2.0'
            out['gi.repository.GLib']['linuxmint'] = 'gir1.2-glib-2.0'
            out['gi.repository.GLib']['ubuntu'] = 'gir1.2-glib-2.0'
        if not GDK_PIXBUF_AVAILABLE:
            out['gtk']['debian'] = 'gir1.2-gdkpixbuf-2.0'
            out['gtk']['linuxmint'] = 'gir1.2-gdkpixbuf-2.0'
            out['gtk']['ubuntu'] = 'gir1.2-gdkpixbuf-2.0'

    def pillow2pixbuf(self, img):
        """
        Convert an image object to a GDK pixbuf
        """
        if img is None:
            return None
        img = img.convert("RGB")

        if hasattr(GdkPixbuf.Pixbuf, 'new_from_bytes'):
            data = GLib.Bytes.new(img.tobytes())
            (width, height) = img.size
            return GdkPixbuf.Pixbuf.new_from_bytes(
                data, GdkPixbuf.Colorspace.RGB,
                False, 8, width, height, width * 3
            )

        file_desc = io.BytesIO()
        try:
            img.save(file_desc, "ppm")
            contents = file_desc.getvalue()
        finally:
            file_desc.close()
        loader = GdkPixbuf.PixbufLoader.new_with_type("pnm")
        try:
            loader.write(contents)
            pixbuf = loader.get_pixbuf()
        finally:
            loader.close()
        return pixbuf
