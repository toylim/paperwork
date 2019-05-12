import collections
import importlib
import logging


LOGGER = logging.getLogger(__name__)


class PluginBase(object):
    """
    Indicates all the methods that must be implemented by any plugin
    managed by OpenPaperwork core. Also provides default implementations.
    """

    # Convenience for the applications: Indicates if users should be able
    # to enable/disable this plugin in the UI.
    USER_VISIBLE = False

    def __init__(self):
        """
        Called as soon as the module is loaded. Should be as minimal as
        possible. Most of the work should be done in `init()`.
        You *must* *not* rely on any dependencies here.
        """
        pass

    def get_implemented_interfaces(self):
        """
        Indicates the list of interfaces implemented by this plugin.
        Interface names are arbitrarily defined. Methods provided by each
        interface are arbitrarily defined (and no checks are done).

        Returns a list of string.
        """
        return []

    def get_deps(self):
        """
        Return the dependencies required by this plugin.
        """
        return {
            'plugins': [],
            'interfaces': [],
        }

    def init(self):
        pass


class Core(object):
    """
    Manage plugins and their callbacks.
    """
    def __init__(self):
        self.explicits = []

        self.plugins = {}
        self._to_initialize = []  # because initialization order matters
        self.interfaces = collections.defaultdict(list)
        self.callbacks = collections.defaultdict(list)

    def load(self, module_name, explicit=False):
        """
        - Load the specified module
        - Instantiate the class 'Plugin()' of this module
        - Register all the methods of this plugin object (except those starting
          by '_' and those from the class PluginBase) as callbacks

        BEWARE of dependency loops !

        Arguments:
            - module_name: name of the Python module to load
            - explicit: this plugin loading has been explicitly requested
              by the user (used to track which modules must possibly be saved
              in a configuration file)
        """
        LOGGER.info(
            "Loading plugin '%s' (explicit=%b) ...",
            module_name, explicit
        )
        module = importlib.import_module(module_name)

        plugin = module.Plugin()
        self.plugins[module_name] = plugin

        for interface in plugin.get_implemented_interfaces():
            LOGGER.debug("- '%s' provides '%s'", module_name, interface)
            self.interfaces[interface].append(plugin)

        for attr_name in dir(plugin):
            if attr_name[0] == "_":
                continue
            if attr_name in dir(PluginBase):  # ignore base methods of plugins
                continue
            attr = getattr(plugin, attr_name)
            if not hasattr(attr, '__call__'):
                continue
            LOGGER.debug("- %s.%s()", module_name, attr_name)
            self.callbacks[attr_name].append(attr)

        if explicit:
            self.explicits.append(module_name)

        self._to_initialize.append(plugin)

        LOGGER.info("Plugin '%s' loaded", module_name)
        return plugin

    def get_explicits(self):
        """
        Returns the list of module names that were loaded explicitly by user
        request. Useful if you want to keep track of those modules in a
        configuration file.
        """
        return tuple(self.explicits)  # makes it immutable

    def _load_deps(self):
        to_examine = list(self.plugins.values())

        while len(to_examine) > 0:
            plugin = to_examine[0]
            to_examine = to_examine[1:]

            LOGGER.info("Examining dependencies of '%s' ...", type(plugin))

            deps = plugin.get_deps()
            if 'plugins' in deps:
                for dep_plugin in deps['plugins']:
                    if dep_plugin in self.plugins:
                        LOGGER.info("- Plugin '%s' already loaded", dep_plugin)
                        continue
                    to_examine.append(self.load(dep_plugin))

            if 'interfaces' in deps:
                for (dep_interface, dep_defaults) in deps['interfaces']:
                    if len(self.interfaces[dep_interface]) > 0:
                        LOGGER.info(
                            "- Interface '%s' already provided by %d plugins",
                            dep_interface, len(self.interfaces[dep_interface])
                        )
                        continue
                    LOGGER.info(
                        "Loading default plugins for interface '%s'"
                        " (%d plugins)",
                        dep_interface, len(dep_defaults)
                    )
                    for dep_default in dep_defaults:
                        to_examine.append(self.load(dep_default))
                    assert(len(self.interfaces[dep_interface]) > 0)

    def _init(self, plugin, initialized=set()):
        if plugin in initialized:
            return

        deps = plugin.get_deps()
        if 'plugins' in deps:
            for dep_plugin in deps['plugins']:
                assert(dep_plugin in self.plugins)
                self._init(self.plugins[dep_plugin], initialized)

        if 'interfaces' in deps:
            for (dep_interface, _) in deps['interfaces']:
                dep_plugins = self.interfaces[dep_interface]
                assert(len(dep_plugins) > 0)
                for dep_plugin in dep_plugins:
                    self._init(dep_plugin, initialized)

        LOGGER.info("Initializing plugin '%s' ...", type(plugin))
        plugin.init()

        initialized.add(plugin)

    def init(self):
        """
        - Make sure all the dependencies of all the plugins are satisfied.
        - Call the method init() of each plugin following the dependency
          order (those without dependencies are called first).

        BEWARE of dependency loops !
        """
        LOGGER.info("Initializing core")
        self._load_deps()
        for plugin in self._to_initialize:
            self._init(plugin)
        self._to_initialize = []
        LOGGER.info("Core initialized")

    def get(self, module_name):
        """
        Returns a Plugin instance based on the corresponding module name
        (assuming it has been loaded).
        """
        return self.plugins[module_name]

    def call_all(self, callback_name, *args, **kwargs):
        """
        Call all the methods of all the plugins that have `callback_name`
        as name. Arguments are passed as is. Returned values are dropped
        (use callbacks for return values if required)
        """
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            LOGGER.warning("No method '%s' available !", callback_name)
        for callback in callbacks:
            callback(*args, **kwargs)

    def call_one(self, callback_name, *args, **kwargs):
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            raise IndexError(
                "No method '{}' available !".format(callback_name)
            )
        if len(callbacks) > 1:
            LOGGER.warning(
                "More than one method '%s' available ! [%s]", callback_name,
                ", ".join([str(callback) for callback in callbacks])
            )
        return callbacks[0](*args, **kwargs)
