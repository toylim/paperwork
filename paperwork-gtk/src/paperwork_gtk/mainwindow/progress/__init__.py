import logging
import math
import threading
import time

import openpaperwork_core
import openpaperwork_core.deps

try:
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    GDK_AVAILABLE = True
except (ImportError, ValueError):
    GDK_AVAILABLE = False


LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = 0.3


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        # A thread updates the widgets every 300ms. We don't update them
        # each time on_progress() is called to not degrade performanes
        self.thread = None
        self.lock = threading.Lock()
        self.progress_widget_trees = {}
        # self.progresses is only used to transmist new progress updates
        # to the thread
        self.progresses = {}
        self.button_widget_tree = None
        self.details_widget_tree = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'progress_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.button_widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.progress",
            "progress_button.glade"
        )
        if self.button_widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return
        self.details_widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.progress",
            "progress_popover.glade"
        )
        if self.details_widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.button_widget_tree.get_object("progress_button").set_popover(
            self.details_widget_tree.get_object(
                "progresses_popover"
            )
        )
        self.button_widget_tree.get_object("progress_icon").connect(
            "draw", self._on_icon_draw
        )

        headerbar = self.core.call_success("docview_get_headerbar")
        button = self.button_widget_tree.get_object("progress_revealer")
        headerbar.pack_end(button)

    def chkdeps(self, out: dict):
        if not GDK_AVAILABLE:
            out['gdk'].update(openpaperwork_core.deps.GDK)

    def _thread(self):
        while self.thread is not None:
            time.sleep(TIME_BETWEEN_UPDATES)
            self.core.call_all("mainloop_execute", self._upd_progress_widgets)

    def _upd_progress_widgets(self):
        with self.lock:
            for (upd_type, (progress, description)) in self.progresses.items():
                r = self._upd_progress_widget(
                    upd_type, progress, description
                )
                if not r:
                    self.thread = None
                    break
            self.progresses = {}

    def _upd_progress_widget(self, upd_type, progress, description):
        if progress >= 1.0:  # deletion of progress
            if upd_type not in self.progress_widget_trees:
                return
            widget_tree = self.progress_widget_trees.pop(upd_type)
            box = self.details_widget_tree.get_object(
                "progresses_box"
            )
            details = widget_tree.get_object("progress_bar")
            box.remove(details)
            details.unparent()
            self.button_widget_tree.get_object("progress_button").queue_draw()

            if len(self.progress_widget_trees) <= 0:
                self.button_widget_tree.get_object(
                    "progress_revealer"
                ).set_reveal_child(False)
                return False
            return True

        if upd_type not in self.progress_widget_trees:  # creation of progress
            widget_tree = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.mainwindow.progress",
                "progress_details.glade"
            )
            box = self.details_widget_tree.get_object(
                "progresses_box"
            )
            box.add(widget_tree.get_object("progress_bar"))
            self.progress_widget_trees[upd_type] = widget_tree
        else:
            widget_tree = self.progress_widget_trees[upd_type]

        # update of progress
        progress_bar = widget_tree.get_object("progress_bar")
        progress_bar.set_fraction(progress)
        progress_bar.set_text(description if description is not None else "")

        self.button_widget_tree.get_object("progress_button").queue_draw()

        self.button_widget_tree.get_object(
            "progress_revealer"
        ).set_reveal_child(True)
        return True

    def on_progress(self, upd_type, progress, description=None):
        with self.lock:
            if progress > 1.0:
                LOGGER.warning(
                    "Invalid progression (%f) for [%s]",
                    progress, upd_type
                )
                progress = 1.0

            self.progresses[upd_type] = (progress, description)

            if self.thread is None:
                self.thread = threading.Thread(target=self._thread)
                self.thread.start()

    def _on_icon_draw(self, drawing_area, cairo_ctx):
        if len(self.progress_widget_trees) <= 0:
            ratio = 1.0
        else:
            ratio = sum([
                widget_tree.get_object("progress_bar").get_fraction()
                for widget_tree in self.progress_widget_trees.values()
            ]) / len(self.progress_widget_trees)

        # Translated in Python from Nautilus source code
        # (2020/02/29: src/nautilus-toolbar.c:on_operations_icon_draw())
        style_context = drawing_area.get_style_context()
        foreground = style_context.get_color(drawing_area.get_state_flags())
        background = foreground
        background.alpha *= 0.3

        w = drawing_area.get_allocated_width()
        h = drawing_area.get_allocated_height()

        Gdk.cairo_set_source_rgba(cairo_ctx, background)
        cairo_ctx.arc(w / 2.0, h / 2.0, min(w, h) / 2.0, 0, 2 * math.pi)
        cairo_ctx.fill()

        cairo_ctx.move_to(w / 2.0, h / 2.0)
        Gdk.cairo_set_source_rgba(cairo_ctx, foreground)
        cairo_ctx.arc(
            w / 2.0, h / 2.0, min(w, h) / 2.0, -math.pi / 2.0,
            (ratio * 2 * math.pi) - (math.pi / 2.0)
        )
        cairo_ctx.fill()
