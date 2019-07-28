"""
Manages a configuration file using configparser.
"""

import collections
import configparser
import logging
import os
import os.path

from . import PluginBase


LOGGER = logging.getLogger(__name__)


class ConfigBool(object):
    def __init__(self, value=False):
        if isinstance(value, str):
            self.value = (value.lower() == 'true')
        else:
            self.value = value

    def __eq__(self, o):
        return (self.value == o)

    def __bool__(self):
        return self.value

    def __str__(self):
        return str(self.value)


class ConfigList(object):
    SEPARATOR = ", "

    def __init__(self, value=None, elements=None):
        if elements is None:
            elements = []
        self.elements = elements

        if value is not None:
            if isinstance(value, str):
                elements = value.split(self.SEPARATOR)
                for i in elements:
                    (t, v) = i.split(_TYPE_SEPARATOR, 1)
                    self.elements.append(_STR_TO_TYPE[t](v))
            elif hasattr(value, 'elements'):
                self.elements = value.elements[:]
            else:
                self.elements = list(value)

    def __iter__(self):
        return iter(self.elements)

    def __contains__(self, o):
        return o in self.elements

    def __getitem__(self, *args, **kwargs):
        return self.elements.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.elements.__setitem__(*args, **kwargs)

    def __len__(self):
        return len(self.elements)

    def append(self, value):
        self.elements.append(value)

    def __str__(self):
        out = []
        for e in self.elements:
            out.append("{}{}{}".format(
                _TYPE_TO_STR[type(e)], _TYPE_SEPARATOR, str(e)
            ))
        return self.SEPARATOR.join(out)


class ConfigDict(object):
    SEPARATOR_ITEMS = ", "
    SEPARATOR_KEYVALS = "="

    def __init__(self, value=None, elements={}):
        self.elements = elements

        if value is not None:
            if isinstance(value, str):
                elements = value.split(self.SEPARATOR_ITEMS)
                for i in elements:
                    (k, v) = i.split(self.SEPARATOR_KEYVALS, 1)
                    (t, v) = v.split(_TYPE_SEPARATOR, 1)
                    self.elements[k] = _STR_TO_TYPE[t](v)
            elif hasattr(value, 'elements'):
                self.elements = value.elements[:]
            else:
                self.elements = dict(value)

    def __iter__(self):
        return iter(self.elements)

    def __contains__(self, o):
        return o in self.elements

    def __getitem__(self, *args, **kwargs):
        return self.elements.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.elements.__setitem__(*args, **kwargs)

    def __len__(self):
        return len(self.elements)

    def __str__(self):
        out = []
        for (k, v) in self.elements.items():
            out.append("{}{}{}{}{}".format(
                k, self.SEPARATOR_KEYVALS,
                _TYPE_TO_STR[type(v)], _TYPE_SEPARATOR, str(v)
            ))
        return self.SEPARATOR_ITEMS.join(out)


_TYPE_TO_STR = {
    bool: "bool",
    ConfigBool: "bool",
    ConfigDict: "dict",
    ConfigList: "list",
    dict: "dict",
    float: "float",
    int: "int",
    list: "list",
    str: "str",
    tuple: "list",
}
_STR_TO_TYPE = {
    "bool": ConfigBool,
    "dict": ConfigDict,
    "list": ConfigList,
    "float": float,
    "int": int,
    "str": str,
}
_TYPE_SEPARATOR = ":"


class Plugin(PluginBase):
    def __init__(self):
        self.config = configparser.RawConfigParser()
        self.base_path = os.getenv(
            "XDG_CONFIG_HOME",
            os.path.expanduser("~/.config")
        )
        self.config_file_path_fmt = os.path.join(
            "{directory}", "{app_name}.conf"
        )
        self.application_name = None
        self.observers = collections.defaultdict(set)
        self.core = None

    def init(self, core):
        self.core = core

    def get_interfaces(self):
        return ['configuration']

    def config_load(self, application_name):
        self.application_name = application_name
        config_path = self.config_file_path_fmt.format(
            directory=self.base_path,
            app_name=application_name,
        )
        self.config = configparser.RawConfigParser()
        LOGGER.info("Loading configuration '%s' ...", config_path)
        with open(config_path, 'r') as fd:
            self.config.read_file(fd)
        for observers in self.observers.values():
            for observer in observers:
                observer()

    def config_save(self, application_name=None):
        if application_name is not None:
            self.application_name = application_name
        config_path = self.config_file_path_fmt.format(
            directory=self.base_path,
            app_name=self.application_name,
        )
        LOGGER.info("Writing configuration '%s' ...", config_path)
        with open(config_path, 'w') as fd:
            self.config.write(fd)

    def config_load_plugins(self, default=[]):
        """
        Load and init the plugin list from the configuration.
        """
        modules = self.config_get(
            "plugins", "modules", ConfigList(None, default)
        )
        LOGGER.info(
            "Loading and initializing plugins from configuration: %s",
            str(modules)
        )
        for module in modules:
            self.core.load(module)
        self.core.init()

    def config_add_plugin(self, module_name):
        LOGGER.info("Adding plugin '%s' to configuration", module_name)
        modules = self.config_get("plugins", "modules", ConfigList())
        modules.elements.append(module_name)
        self.config_put("plugins", "modules", modules)

    def config_remove_plugin(self, module_name):
        LOGGER.info("Removing plugin '%s' from configuration", module_name)
        modules = self.config_get("plugins", "modules", ConfigList())
        modules.elements.remove(module_name)
        self.config_put("plugins", "modules", modules)

    def config_put(self, section, key, value):
        """
        Section must be a string.
        Key must be a string.
        """
        LOGGER.debug("Configuration: %s:%s <-- %s", section, key, str(value))
        t_str = _TYPE_TO_STR[type(value)]
        t = _STR_TO_TYPE[t_str]
        value = t(value)
        value = "{}{}{}".format(t_str, _TYPE_SEPARATOR, str(value))
        if section not in self.config:
            self.config[section] = {key: value}
        else:
            self.config[section][key] = value

        for observer in self.observers[section]:
            observer()

    def config_get(self, section, key, default=None):
        try:
            value = self.config[section][key]
            (t, value) = value.split(_TYPE_SEPARATOR, 1)
            r = _STR_TO_TYPE[t](value)
            LOGGER.debug("Configuration: %s:%s --> %s", section, key, str(r))
            return r
        except KeyError:
            if default is None:
                raise KeyError(
                    "Configuration: {}:{} not found".format(section, key)
                )
            LOGGER.debug(
                "Configuration: %s:%s --> %s (default value)",
                section, key, str(default)
            )
            return default

    def config_add_observer(self, section, callback):
        self.observers[section].add(callback)

    def config_remove_observer(self, section, callback):
        self.observers[section].remove(callback)
