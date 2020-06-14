import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.windows = []
        self.widget_tree = None
        self.groups = {}

    def get_interfaces(self):
        return [
            'app_shortcuts',
            'chkdeps',
            'gtk_shortcut_help',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.shortcutswin", "shortcutswin.glade"
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def gtk_show_shortcuts(self):
        LOGGER.info("Showing shortcuts")
        window = self.widget_tree.get_object("shortcuts")
        window.set_transient_for(self.windows[-1])
        window.show_all()

    def app_shortcut_add(
            self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        self.shortcut_help_add(
            shortcut_group, shortcut_desc, shortcut_keys, action_name
        )

    def shortcut_help_add(
            self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        LOGGER.info(
            "Keyboard shortcut: %s --> %s:%s",
            shortcut_keys, shortcut_group, shortcut_desc
        )

        section = self.widget_tree.get_object("shortcuts_mainwindow")

        group = self.groups.get(shortcut_group, None)
        if group is None:
            group = Gtk.ShortcutsGroup()
            group.set_property("title", shortcut_group)
            group.set_visible(True)
            self.groups[shortcut_group] = group
            section.add(group)

        shortcut = Gtk.ShortcutsShortcut()
        shortcut.set_property("accelerator", shortcut_keys)
        shortcut.set_property("title", shortcut_desc)
        shortcut.set_visible(True)
        group.add(shortcut)
