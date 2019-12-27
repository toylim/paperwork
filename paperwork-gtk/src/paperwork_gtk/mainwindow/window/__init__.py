import collections
import logging

import openpaperwork_core

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ValueError, ImportError):
    GTK_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.stacks = {}
        self.components = collections.defaultdict(dict)
        self.default = collections.defaultdict(
            lambda: (-1, "missing-component")
        )

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_mainwindow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
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

    def init(self, core):
        super().init(core)

        if not GTK_AVAILABLE:
            return

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.window", "mainwindow.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.window", "mainwindow.glade"
        )

        mainwindow = self.widget_tree.get_object("mainwindow")
        mainwindow.connect(
            "destroy", self.on_mainwindow_destroy
        )

        self.stacks = {
            "left": {
                "header": self.widget_tree.get_object(
                    "mainwindow_stack_header_left"
                ),
                "body": self.widget_tree.get_object(
                    "mainwindow_stack_body_left"
                ),
            },
            "right": {
                "header": self.widget_tree.get_object(
                    "mainwindow_stack_header_right"
                ),
                "body": self.widget_tree.get_object(
                    "mainwindow_stack_body_right"
                ),
            },
        }

    def on_initialized(self):
        for (side_name, side_default) in self.default.items():
            if side_default[0] < 0:
                continue
            self.mainwindow_show(side_name, side_default[1])
        self.widget_tree.get_object("mainwindow").set_visible(True)

    def on_mainwindow_destroy(self, main_window):
        LOGGER.info("Main window destroy. Quitting")
        self.core.call_all("mainloop_quit_graceful")

    def mainwindow_add(
                self, side: str,
                name: str, priority: int,
                header, body
            ):

        self.components[side][name] = {
            "header": header,
            "body": body,
        }
        components = self.components[side][name]
        stacks = self.stacks[side]
        for (position, widget) in components.items():
            stacks[position].add_named(widget, name)
        if priority > self.default[side][0]:
            self.default[side] = (priority, name)
        return True

    def mainwindow_show(self, side: str, name: str):
        LOGGER.info("Showing %s on %s", name, side)
        components = self.components[side][name]
        stacks = self.stacks[side]
        for stack in stacks.values():
            stack.set_visible_child_name(name)
        return True
