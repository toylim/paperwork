#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
"""
Paperwork configuration management code
"""

import collections
import gettext
import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext

# Only basic types are handled by shell commands
CMD_VALUE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
}


class Setting(object):
    def __init__(self, core, section, token, default_value_func):
        self.core = core
        self.section = section
        self.token = token
        self.default_value_func = default_value_func

    def get(self):
        value = self.core.call_success(
            "config_backend_get", self.section, self.token, None
        )
        if value is None:
            return self.default_value_func()
        else:
            return value

    def put(self, value):
        self.core.call_all(
            "config_backend_put", self.section, self.token, value
        )


class Plugin(PluginBase):
    """
    Translate values from the configuration into more usable ones.
    Provides default values (except for plugins).
    """

    def __init__(self):
        self.core = None
        self.settings = {}
        self.values = {}
        self.application = None
        self.plugin_list_name = None
        self.observers = collections.defaultdict(set)

    def get_interfaces(self):
        return ['config']

    def get_deps(self):
        return [
            {
                'interface': 'config_backend',
                'defaults': ['openpaperwork_core.config.backend.file'],
            },
        ]

    def init(self, core):
        self.core = core
        self.settings = {}

    def config_load(self, application, plugin_list_name, default_plugins=[]):
        self.application = application
        self.plugin_list_name = plugin_list_name
        self.core.call_all('config_backend_load', application)
        self.core.call_all(
            'config_backend_load_plugins', plugin_list_name, default_plugins
        )

    def config_get_application_name(self):
        return self.application

    def config_get_plugin_list_name(self):
        return self.plugin_list_name

    def config_save(self):
        self.core.call_all('config_backend_save')

    def config_build_simple(
                self, section, token, default_value_func
            ):
        """
        Provide a default simple implementation for a new setting that can
        be registered using 'config_register'.

        Arguments:
          - section: Section in which option must be stored (see ConfigParser)
          - token: token name for the option (see ConfigParser)
          - default_value_func: function to call to get the default value if
            none is stored in the file.
        """
        return Setting(self.core, section, token, default_value_func)

    def config_register(self, key: str, setting):
        """
        Add another setting to manage. Make this setting available to other
        components.

        Arguments:
          - key: configuration key
          - setting: Setting must be an object providing a method `get()`
            and a method `put(value)`. See :func:`config_build_simple` to
            get quickly a default implementation.
        """
        self.settings[key] = setting

    def config_list_options(self):
        return list(self.settings.keys())

    def config_get_setting(self, key: str):
        return self.settings[key]

    def config_get(self, key: str):
        if key not in self.settings:
            return None
        if key not in self.values:
            self.values[key] = self.settings[key].get()
        return self.values[key]

    def config_get_default(self, key: str):
        return self.settings[key].default_value_func()

    def config_put(self, key: str, value):
        """
        Store a setting value.
        Warning: You must call :func:`config_save` so the changes are actually
        saved.

        Arguments:
          - key: configuration key,
          - value: can be of many types (`str`, `int`, etc).
        """
        self.settings[key].put(value)
        self.values[key] = value
        if key in self.observers:
            for callback in self.observers[key]:
                callback(key, value)

    def config_add_plugin(self, plugin, application=None):
        if application is None:
            application = self.application
        self.core.call_all('config_backend_add_plugin', application, plugin)

    def config_remove_plugin(self, plugin, application=None):
        if application is None:
            application = self.application
        self.core.call_all('config_backend_remove_plugin', application, plugin)

    def config_list_plugins(self, application=None):
        if application is None:
            application = self.application
        return self.core.call_success(
            "config_backend_list_active_plugins", application
        )

    def config_reset_plugins(self, application=None):
        if application is None:
            application = self.application
        return self.core.call_success(
            "config_backend_reset_plugins", application
        )

    def config_add_observer(self, key: str, callback):
        self.observers[key].add(callback)

    def config_remove_observer(self, key: str, callback):
        self.observers[key].remove(callback)
