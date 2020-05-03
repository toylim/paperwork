import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['l10n_init']

    def get_deps(self):
        return [
            {
                'interface': 'l10n',
                'defaults': ['openpaperwork_core.l10n.python'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "l10n_load", "paperwork_gtk.l10n", "paperwork_gtk"
        )
