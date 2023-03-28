import gettext

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_page',
            'shortcuts_page_edit',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_page_edit',
                'defaults': ['paperwork_gtk.actions.page.edit'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def init(self, core):
        super().init(core)

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            gettext.pgettext("keyboard shortcut categories", "Page"),
            gettext.pgettext("keyboard shortcut names", "Edit"),
            "<Control><Shift>e", "win.page_edit"
        )
