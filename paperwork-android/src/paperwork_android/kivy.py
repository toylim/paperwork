import logging

import jnius

import kivy
import kivy.core.window
import kivy.lang.builder
import kivy.properties

import kivymd
import kivymd.app

from openpaperwork_core import PluginBase

import paperwork_android.util


LOGGER = logging.getLogger(__name__)


class PaperworkApp(kivymd.app.MDApp):
    media = kivy.properties.OptionProperty('M', options=(
        'XS', 'S', 'M', 'L', 'XL'
    ))
    orientation = kivy.properties.OptionProperty('portrait', options=(
        'portrait', 'landscape'
    ))

    def __init__(self, plugin, **kwargs):
        super().__init__(**kwargs)

        self.previous = (None, None)
        self.root = None
        self.plugin = plugin
        self.navigation_history = []

    def set_theme_style(self):
        python_activity = jnius.autoclass('org.kivy.android.PythonActivity')
        current_activity = python_activity.mActivity
        context = current_activity.getApplicationContext()
        resources = context.getResources()
        configuration = resources.getConfiguration()
        ui_mode = (configuration.uiMode & configuration.UI_MODE_NIGHT_MASK)
        night_mode = (ui_mode == configuration.UI_MODE_NIGHT_YES)
        self.theme_cls.theme_style = "Dark" if night_mode else "Light"

    def build(self):
        self.set_theme_style()

        kivy.core.window.Window.bind(on_keyboard=self.on_key_input)
        kivy.core.window.Window.bind(size=self.on_media_update)

        self.root = kivy.lang.builder.Builder.load_file(
            self.plugin.core.call_success(
                "fs_unsafe",
                self.plugin.core.call_success(
                    "resources_get_file",
                    "paperwork_android", "kivy.kv"
                )
            )
        )
        assert(self.root is not None)
        self.plugin.core.call_all("kivy_load_screens", self.root)
        return self.root

    def on_media_update(self, win, size):
        (width, height) = size
        self.media = (
            'XS' if width < 250 else
            'S' if width < 500 else
            'M' if width < 1000 else
            'L' if width < 1200 else
            'XL'
        )
        self.orientation = "portrait" if (width <= height) else "landscape"
        if (self.media, self.orientation) == self.previous:
            return
        self.previous = (self.media, self.orientation)
        LOGGER.info(
            "Display size change: size=%s, orientation=%s",
            self.media, self.orientation
        )
        self.plugin.core.call_all(
            "on_media_changed", str(self.media), str(self.orientation)
        )

    def goto_window(self, window_name):
        self.root.current = window_name

        if window_name in self.navigation_history:
            self.navigation_history.remove(window_name)
        self.navigation_history.append(window_name)
        LOGGER.info("Navigation history: %s", self.navigation_history)

    def on_key_input(self, window, key, scancode, codepoint, modifier):
        if key not in (27, 1001):  # back button
            return False
        return bool(self.plugin.core.call_success("on_back_key"))

    @paperwork_android.util.async_cb
    async def run(self):
        await self.async_run()
        LOGGER.info("Kivy app has ended")
        self.plugin.core.call_all("mainloop_quit_graceful")


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.app = None

    def get_interfaces(self):
        return [
            'kivy',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
        ]

    def init(self, core):
        super().init(core)
        kivy.require("1.11.1")
        self.app = PaperworkApp(self)

    def on_initialized(self):
        self.app.run()

    def kivy_get_app(self):
        return self.app

    def kivy_get_user_data_dir(self):
        return self.app.user_data_dir

    def goto_window(self, window):
        self.app.goto_window(window)

    def on_back_key(self):
        LOGGER.info(
            "Back button pressed. Current navigation history: %s",
            self.app.navigation_history
        )
        self.app.navigation_history.pop(-1)
        if len(self.app.navigation_history) > 0:
            self.app.root.current = self.app.navigation_history[-1]
        else:
            self.app.stop()
        return True
