import openpaperwork_core


class PaperworkSetting(object):
    def __init__(self, value, default_func):
        self.value = value
        self.default_value_func = default_func

    def get(self):
        if self.value is None:
            return self.default_value_func()
        return self.value

    def put(self, v):
        sel.value = v


class Plugin(openpaperwork_core.PluginBase):
    """
    Translate values from the configuration into more usable ones.
    Provides default values (except for plugins).
    """

    def __init__(self):
        super().__init__()
        self._settings = {}

    def __get_settings(self):
        return {k: v.get() for (k, v) in self._settings.items()}

    def __set_settings(self, new_settings):
        self._settings = {
            k: PaperworkSetting(v, lambda: None)
            for (k, v) in new_settings.items()
        }

    settings = property(__get_settings, __set_settings)

    def get_interfaces(self):
        return ['paperwork_config']

    def paperwork_config_load(self, application, default_plugins=[]):
        pass

    def paperwork_config_save(self):
        raise NotImplementedError()

    def paperwork_config_build_simple(self, section, token, default):
        return PaperworkSetting(None, None, default)

    def paperwork_config_register(self, key, setting):
        self._settings[key] = setting

    def paperwork_config_get_setting(self, key):
        return self._settings[key]

    def paperwork_config_get(self, key):
        return self._settings[key].get()

    def paperwork_config_get_default(self, key):
        return self._settings[key].default_value_func()

    def paperwork_config_put(self, key, value):
        self._settings[key].put(value)

    def paperwork_add_plugin(self, plugin):
        raise NotImplementedError()

    def paperwork_remove_plugin(self, plugin):
        raise NotImplementedError()
