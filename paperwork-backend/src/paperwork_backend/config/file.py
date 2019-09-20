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

import gettext
import logging
import os

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext

# Only basic types are handled by shell commands
CMD_VALUE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
}


class PaperworkSetting(object):
    def __init__(self, core, section, token, default_value_func):
        self.core = core
        self.section = section
        self.token = token
        self.default_value_func = default_value_func

    def get(self):
        value = self.core.call_success(
            "config_get", self.section, self.token, None
        )
        if value is None:
            return self.default_value_func()
        else:
            return value

    def put(self, value):
        self.core.call_all(
            "config_put", self.section, self.token, value
        )


class Plugin(openpaperwork_core.PluginBase):
    """
    Translate values from the configuration into more usable ones.
    Provides default values (except for plugins).
    """

    def __init__(self):
        self.core = None
        self.settings = {}
        self.values = {}
        self.application = None

    def get_interfaces(self):
        return ['paperwork_config']

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio']),
                ('configuration', ['openpaperwork_core.config_file']),
            ],
        }

    def init(self, core):
        self.core = core
        self.settings = {
            'workdir': PaperworkSetting(
                core, "Global", "WorkDirectory",
                lambda: self.core.call_success(
                    "fs_safe", os.path.expanduser("~/papers")
                )
            ),
            'index_version': PaperworkSetting(
                core, "Global", "IndexVersion", lambda: "-1"
            ),
            'index_in_workdir': PaperworkSetting(
                core, "Global", "index_in_workdir",
                lambda: False
            ),
        }

    def paperwork_config_load(self, application, default_plugins=[]):
        self.application = application
        self.core.call_all('config_load', 'paperwork')
        self.core.call_all('config_load_plugins', application, default_plugins)

    def paperwork_get_application_name(self):
        return self.application

    def paperwork_config_save(self):
        self.core.call_all('config_save')

    def paperwork_config_build_simple(
                self, section, token, default_value_func
            ):
        """
        Provide a default simple implementation for a new setting that can
        be registered using 'paperwork_config_register'.

        Arguments:
        - section: Section in which option must be stored (see ConfigParser)
        - token: token name for the option (see ConfigParser)
        - default_value_func: function to call to get the default value if
          none is stored in the file.
        """
        return PaperworkSetting(self.core, section, token, default_value_func)

    def paperwork_config_register(self, key, setting):
        """
        Add another setting to manage. Make this setting available to other
        components.
        """
        self.settings[key] = setting

    def paperwork_config_get_setting(self, key):
        return self.settings[key]

    def paperwork_config_get(self, key):
        if key not in self.settings:
            return None
        if key not in self.values:
            self.values[key] = self.settings[key].get()
        return self.values[key]

    def paperwork_config_get_default(self, key):
        return self.settings[key].default_value_func()

    def paperwork_config_put(self, key, value):
        self.settings[key].put(value)
        self.values[key] = value

    def paperwork_add_plugin(self, plugin):
        self.core.call_all('config_add_plugin', self.application, plugin)

    def paperwork_remove_plugin(self, plugin):
        self.core.call_all('config_remove_plugin', self.application, plugin)
