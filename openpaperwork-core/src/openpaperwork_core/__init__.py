import collections
import importlib
import logging


LOGGER = logging.getLogger(__name__)


class DependencyException(Exception):
    pass


class PluginBase(object):
    """
    Indicates all the methods that must be implemented by any plugin
    managed by OpenPaperwork core. Also provides default implementations
    for each method.
    """

    # Priority defines in which order callbacks will be called.
    # Plugins with higher priorities will have their callbacks called first.
    PRIORITY = 0

    # Convenience for the applications: Indicates if users should be able
    # to enable/disable this plugin in the UI.
    USER_VISIBLE = False

    def __init__(self):
        """
        Called as soon as the module is loaded. Should be as minimal as
        possible. Most of the work should be done in `init()`.
        You *must* *not* rely on any dependencies here.
        """
        self.core = None

    def get_interfaces(self):
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

        Example:

        .. code-block:: python

          [
            {
              "interface": "some_interface_name",  # required
              "defaults": ['plugin_a', 'plugin_b'],  # required
              "expected_already_satisfied": False,  # optional, default: True
            },
          ]
        """
        return []

    def init(self, core):
        # default implementation
        self.core = core


class Core(object):
    """
    Manage plugins and their callbacks.
    """
    def __init__(self, allow_unsatisfied=False):
        self.plugins = {}
        self._to_initialize = set()
        self._initialized = set()  # avoid double-init
        self.interfaces = collections.defaultdict(list)
        self.callbacks = collections.defaultdict(list)
        self.allow_unsatisfied = allow_unsatisfied

    def load(self, module_name):
        """
        - Load the specified module
        - Instantiate the class 'Plugin()' of this module
        - Register all the methods of this plugin object (except those starting
          by '_' and those from the class PluginBase) as callbacks

        BEWARE of dependency loops !

        Arguments:
            - module_name: name of the Python module to load
        """
        if module_name in self.plugins:
            return self.plugins[module_name]

        LOGGER.info("Loading plugin '%s' ...", module_name)
        module = importlib.import_module(module_name)
        return self._load_module(module_name, module)

    def _load_module(self, module_name, module):
        """
        should be called from outside for testing only
        """
        if module_name in self.plugins:
            LOGGER.debug("Module %s already loaded", module_name)
            return self.plugins[module_name]

        plugin = module.Plugin()
        self.plugins[module_name] = plugin

        for interface in plugin.get_interfaces():
            LOGGER.debug("- '%s' provides '%s'", module_name, interface)
            self.interfaces[interface].append(plugin)

        for attr_name in dir(plugin):
            if attr_name[0] == "_":
                continue
            if attr_name in dir(PluginBase):  # ignore base methods of plugins
                continue
            callback = getattr(plugin, attr_name)
            if not hasattr(callback, '__call__'):
                continue
            LOGGER.debug("- %s.%s()", module_name, attr_name)
            self.callbacks[attr_name].append((
                plugin.PRIORITY, str(type(plugin)), callback
            ))
            self.callbacks[attr_name].sort(reverse=True)

        self._to_initialize.add(plugin)

        LOGGER.info("Plugin '%s' loaded", module_name)
        return plugin

    def _check_deps(self):
        to_examine = [
            (plugin_name, plugin)
            for (plugin_name, plugin) in self.plugins.items()
        ]

        while len(to_examine) > 0:
            (plugin_name, plugin) = to_examine[0]
            to_examine = to_examine[1:]

            LOGGER.info("Examining dependencies of '%s' ...", plugin_name)

            deps = plugin.get_deps()
            for dep in deps:
                interface = dep['interface']
                if len(self.interfaces[interface]) > 0:
                    LOGGER.debug(
                        "- Interface '%s' already provided by %d plugins",
                        interface, len(self.interfaces[interface])
                    )
                    continue

                defaults = dep['defaults']
                if len(defaults) <= 0:
                    continue

                if (not self.allow_unsatisfied
                        and (
                            'expected_already_satisfied' not in dep
                            or dep['expected_already_satisfied']
                        )):
                    LOGGER.warning(
                        "Plugin '{}' requires interface '{}' but no plugins"
                        " provide this interface (suggested: {}). Plugin '{}'"
                        " will be unloaded.".format(
                            plugin_name, interface, defaults, plugin_name
                        )
                    )
                    self.plugins.pop(plugin_name)
                    # return False to indicate we actually dropped a plugin
                    # and need to reevaluate all the dependencies again.
                    return False
                else:
                    LOGGER.info(
                        "Loading plugins %s to satisfy dependency."
                        " Required by '%s' for interface '%s'",
                        defaults, type(plugin), interface
                    )
                    for default in defaults:
                        to_examine.append((default, self.load(default)))

        return True

    def _init(self, plugin):
        if plugin in self._initialized:
            return

        deps = plugin.get_deps()
        for dep in deps:
            dep_plugins = self.interfaces[dep['interface']]
            for dep_plugin in dep_plugins:
                self._init(dep_plugin)

        LOGGER.info("Initializing plugin '%s' ...", type(plugin))
        plugin.init(self)

        self._initialized.add(plugin)

    def init(self):
        """
        - Make sure all the dependencies of all the plugins are satisfied.
        - Call the method init() of each plugin following the dependency
          order (those without dependencies are called first).

        BEWARE of dependency loops !
        """
        LOGGER.info("Initializing all plugins")
        while not self._check_deps():
            pass
        for plugin in self._to_initialize:
            self._init(plugin)
        self._to_initialize = set()
        LOGGER.info("All plugins initialized")

    def get_by_name(self, module_name):
        """
        Returns a Plugin instance based on the corresponding module name
        (assuming it has been loaded).
        """
        return self.plugins[module_name]

    def get_by_interface(self, interface_name):
        return self.interfaces[interface_name]

    def call_all(self, callback_name, *args, **kwargs):
        """
        Call all the methods of all the plugins that have `callback_name`
        as name. Arguments are passed as is. Returned values are dropped
        (use callbacks for return values if required)
        """
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            if callback_name.startswith("on_"):
                # those are 'observer' callback. If nobody is observing,
                # it's usually fine.
                log_method = LOGGER.debug
            else:
                log_method = LOGGER.warning
            log_method("No method '%s' found", callback_name)
            return 0
        for (priority, plugin, callback) in callbacks:
            callback(*args, **kwargs)
        return len(callbacks)

    def call_one(self, callback_name, *args, **kwargs):
        """
        Look for a plugin method called `callback_name` and calls it.
        Raises an error if no such method exists. If many exists,
        raises a warning and call one at random.
        Returns the value return by the callback.

        You're advised to use `call_all()` or `call_success` instead
        whenever possible. This method is only provided as convenience for
        when you're fairly sure there should be only one plugin with such
        callback (example: mainloop plugins).
        """
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            raise IndexError(
                "No method '{}' found !".format(callback_name)
            )
        if len(callbacks) > 1:
            LOGGER.warning(
                "More than one method '%s' found ! [%s]", callback_name,
                ", ".join([callback[1] for callback in callbacks])
            )
        return callbacks[0][2](*args, **kwargs)

    def call_success(self, callback_name, *args, **kwargs):
        """
        Call methods of all the plugins that have `callback_name`
        as name until one of them return a value that is not None.
        Arguments are passed as is. First value to be different
        from None is returned. If none of the callbacks returned
        a value different from None or if no callback has the
        specified name, this method will return None.
        """
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            LOGGER.warning("No method '%s' found", callback_name)
        for (priority, plugin, callback) in callbacks:
            try:
                r = callback(*args, **kwargs)
            except Exception:
                LOGGER.error("Callback '%s' failed", str(callback))
                raise
            if r is not None:
                return r
        return None
