import logging

import kivy
import kivy.lang.builder
import kivymd.uix.list

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.root = None

    def get_interfaces(self):
        return [
            'settings_window',
            'kivy_screen'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'kivy',
                'defaults': ['paperwork_android.kivy'],
            },
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
        ]

    def kivy_load_screens(self, screen_manager):
        self.root = kivy.lang.builder.Builder.load_file(
            self.core.call_success(
                "fs_unsafe",
                self.core.call_success(
                    "resources_get_file",
                    "paperwork_android.settings", "settings.kv"
                )
            )
        )

        # list of (callback, text, subtext)
        settings = []
        self.core.call_all("settings_get", settings)
        LOGGER.info("Got %d settings", len(settings))

        for setting in settings:
            item = kivymd.uix.list.TwoLineListItem(
                text=setting[1],
                secondary_text=setting[2],
                on_release=setting[0]
            )
            self.root.ids.settings_list.add_widget(item)

        screen_manager.add_widget(self.root)
