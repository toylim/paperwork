import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000

    def get_interfaces(self):
        return ['setting']

    def get_deps(self):
        return [
            {
                'interface': 'settings_window',
                'defaults': ['paperwork_android.settings'],
            },
        ]

    def _select_work_directory(self, item):
        # TODO
        pass

    def settings_get(self, settings: dict):
        settings.append(
            (
                self._select_work_directory,
                "Work directory",
                "Directory where all your documents are stored"
            )
        )
