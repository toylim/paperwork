import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_app',
            'shortcuts_app_find',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_app_find',
                'defaults': ['paperwork_gtk.actions.app.find'],
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
            _("Global"), _("Find"),
            "<Control>f", "win.app_find"
        )

        # TODO
        # self.core.call_all(
        #     "app_shortcut_add",
        #     _("Global"), _("Find the next match"),
        #     "<Control>G", "win.app_find_next"
        # )
        # self.core.call_all(
        #     "app_shortcut_add",
        #     _("Global"), _("Find the previous match"),
        #     "<Control><Shift>G", "win.app_find_prev"
        # )
