import logging


try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


import openpaperwork_core

from . import deps


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
            out['gtk'].update(deps.GTK)

    def gtk_load_widget_tree(self, pkg, filename):
        """
        Load a .glade file

        Arguments:
            pkg -- Python package name
            filename -- css file name to load

        Returns:
            GTK Widget Tree
        """

        if not GTK_AVAILABLE:
            LOGGER.error("gtk_load_widget_tree(): GTK is not available")
            return None

        LOGGER.debug("Loading GTK widgets from %s:%s", pkg, filename)

        filepath = self.core.call_success("resources_get_file", pkg, filename)
        with self.core.call_success("fs_open", filepath, 'r') as fd:
            content = fd.read()
        return Gtk.Builder.new_from_string(content, -1)

    def gtk_load_css(self, pkg, filename):
        """
        Load a .css file

        Arguments:
            pkg -- Python package name
            filename -- css file name to load.
        """
        if not GTK_AVAILABLE:
            LOGGER.error("gtk_load_css(): GTK is not available")
            return None

        LOGGER.debug("Loading CSS from %s:%s", pkg, filename)

        filepath = self.core.call_success("resources_get_file", pkg, filename)
        with self.core.call_success("fs_open", filepath, 'rb') as fd:
            content = fd.read()

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(content)

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        return True
