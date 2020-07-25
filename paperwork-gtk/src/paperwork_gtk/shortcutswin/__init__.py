import collections
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
        self.groups = collections.defaultdict(list)
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'app_shortcuts',
            'chkdeps',
            'gtk_shortcut_help',
            'gtk_window_listener',
            'screenshot_provider',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

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
        group = self.groups[shortcut_group]
        group.append((
            shortcut_desc, shortcut_keys, action_name
        ))

    def gtk_show_shortcuts(self):
        LOGGER.info("Showing shortcuts")
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.shortcutswin", "shortcutswin.glade"
        )
        section = self.widget_tree.get_object("shortcuts_mainwindow")
        window = self.widget_tree.get_object("shortcuts")

        groups = {}
        for shortcut_group in sorted(list(self.groups.keys())):
            group = Gtk.ShortcutsGroup()
            group.set_property("title", shortcut_group)
            group.set_visible(True)
            groups[shortcut_group] = group
            section.add(group)

        for (shortcut_group, shortcuts) in self.groups.items():
            group = groups[shortcut_group]
            shortcuts = sorted(list(shortcuts))
            for (shortcut_desc, shortcut_keys, actions_name) in shortcuts:
                shortcut = Gtk.ShortcutsShortcut()
                shortcut.set_property("accelerator", shortcut_keys)
                shortcut.set_property("title", shortcut_desc)
                shortcut.set_visible(True)
                group.add(shortcut)

        window.set_transient_for(self.windows[-1])
        window.show_all()

    def gtk_hide_shortcuts(self):
        if self.widget_tree is None:
            return
        window = self.widget_tree.get_object("shortcuts")
        window.destroy()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            "screenshot_snap_widget", self.widget_tree.get_object("shortcuts"),
            self.core.call_success("fs_join", out_dir, "shortcuts.png"),
        )
