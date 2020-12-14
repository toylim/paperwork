import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return ['sync_on_start']

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        setting = self.core.call_success(
            "config_build_simple", "GUI", "sync_on_start",
            default_value_func=lambda: True
        )
        self.core.call_all("config_register", "sync_on_start", setting)

    def on_initialized(self):
        r = self.core.call_success("config_get", "sync_on_start")
        if r:
            LOGGER.info("Starting synchronization ...")
            self.core.call_all("transaction_sync_all")
        else:
            LOGGER.info("Synchronization on start is disabled.")
