import logging

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

    def build(self):
        kivy.core.window.Window.bind(size=self.update_media)
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

    def update_media(self, win, size):
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

    @paperwork_android.util.async_cb
    async def run(self):
        await self.async_run()


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
        kivy.require("2.0.0")
        self.app = PaperworkApp(self)

    def on_initialized(self):
        self.app.run()

    def kivy_get_app(self):
        return self.app
