import os

import openpaperwork_core
import openpaperwork_core.deps


GI_AVAILABLE = False
GLIB_AVAILABLE = False
POPPLER_AVAILABLE = False


try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'poppler',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'] = openpaperwork_core.deps.POPPLER

    def poppler_open(self, url, password=None):
        if os.name == "nt":
            # WORKAROUND(Jflesch):
            # Disabled for now on Windows: There is a file descriptor leak
            # somewhere.
            # While it causes little problems on GNU/Linux, on Windows it
            # prevents deleting documents.
            return None

        gio_file = Gio.File.new_for_uri(url)
        doc = self.core.call_one(
            "mainloop_execute", Poppler.Document.new_from_gfile,
            gio_file, password=password
        )
        self.core.call_all("on_objref_track", doc)
        return doc
