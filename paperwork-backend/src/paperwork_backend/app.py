import openpaperwork_core

from . import _version


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['app']

    def app_get_name(self):
        return "Paperwork"

    def app_get_version(self):
        return _version.version
