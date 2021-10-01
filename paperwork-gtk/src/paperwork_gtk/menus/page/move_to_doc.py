import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_move_to_doc"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 900

    def get_interfaces(self):
        return [
            'chkdeps',
            'menu',
            'menu_page',
            'menu_page_move_to_text',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_page_move_to_doc',
                'defaults': ['paperwork_gtk.actions.page.move_to_doc'],
            },
            {
                'interface': 'page_actions',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageinfo.actions'
                ],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_page_menu_ready(self):
        item = Gio.MenuItem.new(
            _("Another document"), "win." + ACTION_NAME
        )
        self.core.call_all(
            "page_menu_append_item", item, submenu_name=_("Move page to")
        )
