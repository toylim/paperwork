import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_prev_next',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_doc_prev_next',
                'defaults': ['paperwork_gtk.actions.doc.prev_next'],
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
            _("Document list"), _("Open next document"),
            "<Control>Page_Down", "win.doc_next"
        )
        self.core.call_all(
            "app_shortcut_add",
            _("Document list"), _("Open previous document"),
            "<Control>Page_Up", "win.doc_prev"
        )
