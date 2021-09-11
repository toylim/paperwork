import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'doclist',
            'kivy_build_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
            {
                'interface': 'mainwindow',
                'defaults': ['paperwork_android.mainwindow.window'],
            },
        ]

    def on_kivy_build(self):
        pass
