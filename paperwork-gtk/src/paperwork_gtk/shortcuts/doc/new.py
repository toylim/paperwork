import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_copy_text',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_doc_new',
                'defaults': ['paperwork_gtk.actions.doc.new'],
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
            _("Global"), _("Create new document"),
            "<Control>N", "win.doc_new"
        )
