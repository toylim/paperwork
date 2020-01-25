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
        self.mainwindow = None

    def get_interfaces(self):
        return [
            'app_actions',
            'gtk_mainwindow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow", "global.css"
        )

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

        opt = self.core.call_success(
            "config_build_simple", "GUI", "main_window_size",
            lambda: (1024, 600)
        )
        self.core.call_all("config_register", "main_window_size", opt)
        main_win_size = self.core.call_success(
            "config_get", "main_window_size"
        )

        self.mainwindow = self.widget_tree.get_object("mainwindow")
        self.mainwindow.set_default_size(main_win_size[0], main_win_size[1])
        self.mainwindow.connect("destroy", self._on_mainwindow_destroy)
        self.mainwindow.connect(
            "size-allocate", self._on_mainwindow_size_allocate
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

    def on_quit(self):
        # needed to save window size
        # TODO(JFlesch): not really config --> should not be stored in config ?
        self.core.call_all("config_save")

    def _on_mainwindow_destroy(self, main_window):
        LOGGER.info("Main window destroy. Quitting")
        self.core.call_all("mainloop_quit_graceful")

    def _on_mainwindow_size_allocate(self, main_win, rectangle):
        (w, h) = main_win.get_size()
        self.core.call_all("config_put", "main_window_size", (w, h))

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

    def mainwindow_set_transient_for(self, dialog):
        dialog.set_transient_for(self.mainwindow)
        return True

    def actions_app_add(self, action):
        if self.mainwindow is not None:
            self.mainwindow.add_action(action)
