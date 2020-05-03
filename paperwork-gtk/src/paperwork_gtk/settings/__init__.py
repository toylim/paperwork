import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_windows = []
        self.settings_dialog = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_settings_dialog',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Settings"), "win.open_settings")
        self.core.call_all("menu_app_append_item", item)

        action = Gio.SimpleAction.new('open_settings', None)
        action.connect("activate", self.open_settings)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def open_settings(self, *args, **kwargs):
        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.settings", "settings.css"
        )

        global_widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings", "settings.glade"
        )
        self.core.call_all('complete_settings', global_widget_tree)
        settings = global_widget_tree.get_object("settings_window")
        self.settings_dialog = settings
        settings.set_transient_for(self.active_windows[-1])
        settings.set_modal(True)
        settings.connect("destroy", self._save_settings, global_widget_tree)
        settings.set_visible(True)
        self.core.call_all("on_gtk_window_opened", settings)

    def close_settings(self):
        if self.settings_dialog is not None:
            self.settings_dialog.set_visible(False)
            self.settings_dialog = None

    def on_quit(self):
        self.close_settings()

    def _save_settings(self, window, global_widget_tree):
        LOGGER.info("Settings closed. Saving configuration")
        self.core.call_all("config_save")
        self.core.call_all("on_gtk_window_closed", window)
        self.core.call_all("on_settings_closed", global_widget_tree)
        self.settings_dialog = None

    def add_setting_to_dialog(self, global_widget_tree, title, widgets):
        """
        Add a setting or a set of settings to the main screen in the settings
        dialog.
        """
        # We have many setting boxes to add to the settings box.
        # --> we need many copies of the setting box --> we load many times
        # the widget tree
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings", "settings_section.glade"
        )
        widget_tree.get_object("setting_section_name").set_text(title)
        inner = widget_tree.get_object("setting_box")
        for widget in widgets:
            inner.pack_start(widget, expand=False, fill=True, padding=0)
        global_widget_tree.get_object("settings_box").pack_start(
            widget_tree.get_object("setting_section"),
            expand=False, fill=True, padding=0
        )
        return True

    def add_setting_screen(
            self, global_widget_tree, name, widget_header, widget_body):
        global_widget_tree.get_object("settings_stack_header").add_named(
            widget_header, name
        )
        global_widget_tree.get_object("settings_stack_body").add_named(
            widget_body, name
        )

    def show_setting_screen(self, global_widget_tree, name):
        global_widget_tree.get_object(
            "settings_stack_header"
        ).set_visible_child_name(name)
        global_widget_tree.get_object(
            "settings_stack_body"
        ).set_visible_child_name(name)
