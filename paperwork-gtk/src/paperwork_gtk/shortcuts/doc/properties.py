import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_properties',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_doc_properties',
                'defaults': ['paperwork_gtk.actions.doc.properties'],
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
            _("Document"), _("Edit document properties"),
            "<Control>e", "win.doc_properties"
        )
