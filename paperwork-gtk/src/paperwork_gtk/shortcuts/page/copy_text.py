import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_page',
            'shortcuts_page_copy_text',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_page_copy_text',
                'defaults': ['paperwork_gtk.actions.page.copy_text'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "app_shortcut_add",
            _("Page"), _("Copy selected text to clipboard"),
            "<Control>c", "win.page_copy_text"
        )
