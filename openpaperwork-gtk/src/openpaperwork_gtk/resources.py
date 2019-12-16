import logging


try:
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_resources'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk']['debian'] = 'gir1.2-gtk-3.0'
            out['gtk']['fedora'] = 'gtk3'
            out['gtk']['gentoo'] = 'x11-libs/gtk+'
            out['gtk']['linuxmint'] = 'gir1.2-gtk-3.0'
            out['gtk']['ubuntu'] = 'gir1.2-gtk-3.0'
            out['gtk']['suse'] = 'python-gtk'

    def gtk_load_widget_tree(self, pkg, filename):
        assert(GTK_AVAILABLE)

        filepath = self.core.call_success("resources_get_file", pkg, filename)
        with self.core.call_success("fs_open", filepath, 'r') as fd:
            content = fd.read()
        return Gtk.Builder.new_from_string(content, -1)
