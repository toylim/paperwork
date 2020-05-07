import openpaperwork_core
import openpaperwork_core.deps

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        GLIB_AVAILABLE = False

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        POPPLER_AVAILABLE = False


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'poppler',
        ]

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'] = openpaperwork_core.deps.POPPLER

    def poppler_open(self, url):
        gio_file = Gio.File.new_for_uri(url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
        self.core.call_all("on_objref_track", doc)
        return doc
