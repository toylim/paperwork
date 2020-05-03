import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_open_help',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'help_documents',
                'defaults': ['paperwork_gtk.model.help'],
            },
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        menu = Gio.Menu()
        for (title, file_name) in self.core.call_success("help_get_files"):
            item = Gio.MenuItem.new(title, "win.open_help." + file_name)
            menu.append_item(item)
            action = Gio.SimpleAction.new('open_help.' + file_name, None)
            action.connect("activate", self.doc_open_help, file_name)
            self.core.call_all("app_actions_add", action)
        self.core.call_all("menu_app_append_submenu", _("Help"), menu)

    def doc_open_help(self, action, parameter, file_name):
        doc_url = self.core.call_success("help_get_file", file_name)
        self.core.call_all("doc_open", "help_" + file_name, doc_url)
