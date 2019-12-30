import collections
import logging

import openpaperwork_core


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

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.window", "mainwindow.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.window", "mainwindow.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

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

    def mainwindow_get_main_container(self):
        return self.widget_tree.get_object("main_box")

    def mainwindow_add(self, side: str, name: str, prio: int, header, body):
        self.components[side][name] = {
            "header": header,
            "body": body,
        }
        components = self.components[side][name]
        stacks = self.stacks[side]
        for (position, widget) in components.items():
            stacks[position].add_named(widget, name)
        if prio > self.default[side][0]:
            self.default[side] = (prio, name)
        return True

    def mainwindow_show(self, side: str, name: str):
        LOGGER.info("Showing %s on %s", name, side)
        stacks = self.stacks[side]
        for stack in stacks.values():
            stack.set_visible_child_name(name)
        return True
