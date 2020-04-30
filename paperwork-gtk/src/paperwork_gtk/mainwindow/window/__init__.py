import collections
import gettext
import logging

try:
    from gi.repository import Gio
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import PIL
import PIL.Image
import PIL.ImageDraw

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


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
        self._mainwindow_size = None

    def get_interfaces(self):
        return [
            'app_actions',
            'chkdeps',
            'gtk_mainwindow',
            'screenshot_provider',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
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

        if hasattr(GLib, 'set_application_name'):
            GLib.set_application_name(_("Paperwork"))
        GLib.set_prgname("paperwork")

        app = Gtk.Application(
            application_id=None,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        app.register(None)
        Gtk.Application.set_default(app)
        self.mainwindow.set_application(app)

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

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_initialized(self):
        for (side_name, side_default) in self.default.items():
            if side_default[0] < 0:
                continue
            self.mainwindow_show(side_name, side_default[1])

        self.widget_tree.get_object("mainwindow").set_visible(True)
        self.core.call_all("on_gtk_window_opened", self.mainwindow)

    def on_quit(self):
        # needed to save window size
        # TODO(JFlesch): not really config --> should not be stored in config ?
        if self.mainwindow is not None:
            self.core.call_all("config_save")
            self.mainwindow.set_visible(False)

    def _on_mainwindow_destroy(self, main_window):
        LOGGER.info("Main window destroy. Quitting")
        self.core.call_all("on_gtk_window_closed", self.mainwindow)
        self.core.call_all("mainloop_quit_graceful")

    def _on_mainwindow_size_allocate(self, main_win, rectangle):
        (w, h) = main_win.get_size()
        if self._mainwindow_size == (w, h):
            return
        self._mainwindow_size = (w, h)
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
            if widget is None:
                continue
            stacks[position].add_named(widget, name)
        if prio > self.default[side][0]:
            self.default[side] = (prio, name)
        return True

    def mainwindow_show(self, side: str, name: str):
        LOGGER.info("Showing %s on %s", name, side)
        stacks = self.stacks[side]
        components = self.components[side][name]
        for (h, stack) in stacks.items():
            if h not in components or components[h] is None:
                continue
            stack.set_visible_child_name(name)
        return True

    def mainwindow_show_default(self, side: str):
        self.core.call_all("mainwindow_show", side, self.default[side][1])

    def app_actions_add(self, action):
        if self.mainwindow is not None:
            self.mainwindow.add_action(action)

    def mainwindow_focus(self):
        self.mainwindow.grab_focus()

    def _draw_overlay(self, img, area, color):
        overlay = PIL.Image.new('RGBA', img.size, color + (0,))
        draw = PIL.ImageDraw.Draw(overlay)
        draw.rectangle(area, fill=color + (0x5F,))
        return PIL.Image.alpha_composite(img, overlay)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        out = self.core.call_success("fs_join", out_dir, "main_window.png")
        self.core.call_success(
            "screenshot_snap_widget", self.mainwindow, out
        )

        left = self.stacks['left']['body']
        left_alloc = left.get_allocation()
        left_width = left_alloc.width
        (left_x, _) = left.translate_coordinates(self.mainwindow, 0, 0)
        left = left_x + left_width

        with self.core.call_success("fs_open", out, 'rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            img = img.convert("RGBA")

        img = self._draw_overlay(
            img, (0, 0, left, img.size[1]), (0, 0xFF, 0)
        )
        img = self._draw_overlay(
            img, (left, 0, img.size[0], img.size[1]), (0, 0, 0xFF)
        )

        # drop some black border in the scn
        img = img.crop(
            (left_x, left_x, img.size[0] - left_x, img.size[1] - left_x)
        )

        # keep only the top 150px
        img = img.crop((0, 0, img.size[0], min(300, img.size[1])))

        out = self.core.call_success(
            "fs_join", out_dir, "main_window_split.png"
        )
        with self.core.call_success("fs_open", out, 'wb') as fd:
            img.save(fd, format="PNG")
