import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 1000

    def config_load_plugins(self, plugin_list_name, default_plugins=[]):
        old_default = self.core.call_success(
            "config_backend_get", "default_plugins", plugin_list_name, None
        )
        if old_default is None:
            # no previously known list of default plugins. Weird but not much
            # we can do about it.
            self.core.call_all(
                "config_backend_put",
                "default_plugins", plugin_list_name, default_plugins
            )
            self.core.call_all("config_backend_save")
            return

        old_default = sorted(old_default)
        default_plugins = sorted(default_plugins)

        if old_default == default_plugins:
            # default list hasn't changed. So we assume the custom list
            # is still fine.
            return

        LOGGER.warning(
            "Default plugin list has changed."
            " Reseting plugin list to its new default."
        )
        LOGGER.warning("Old default list: %s", old_default)
        LOGGER.warning("New default list: %s", default_plugins)

        self.core.call_all("config_backend_reset_plugins", plugin_list_name)
        self.core.call_all(
            "config_backend_put",
            "default_plugins", plugin_list_name, default_plugins
        )
        self.core.call_all("config_backend_save")
