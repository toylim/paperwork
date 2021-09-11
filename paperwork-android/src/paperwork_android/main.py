import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

CONFIG_PLUGINS = [
    'openpaperwork_core.archives',
    'openpaperwork_core.cmd.config',
    'openpaperwork_core.cmd.plugins',
    'openpaperwork_core.config',
    'openpaperwork_core.config.automatic_plugin_reset',
    'openpaperwork_core.config.backend.configparser',
    'openpaperwork_core.data_versioning',
    'openpaperwork_core.display.print',
    'openpaperwork_core.fs.python',
    'openpaperwork_core.logs.archives',
    'openpaperwork_core.logs.print',
    'openpaperwork_core.mainloop.asyncio',
    'openpaperwork_core.uncaught_exception',
    'paperwork_backend.app',

    # paperwork_android
    'paths',
]

DEFAULT_PLUGINS = [
]


def main():
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin logs.print first.

    core = openpaperwork_core.Core()
    for module_name in CONFIG_PLUGINS:
        core.load(module_name)
    core.init()
    core.call_all("init_logs", "paperwork-android", "info")

    core.call_all("config_load")
    core.call_all("config_load_plugins", "paperwork-android", DEFAULT_PLUGINS)

    core.call_all("on_initialized")

    LOGGER.info("Ready")
    core.call_one("mainloop", halt_on_uncaught_exception=False)
    LOGGER.info("Quitting")
    core.call_all("config_save")
    core.call_all("on_quit")


if __name__ == "__main__":
    main()
