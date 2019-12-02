# OpenPaperwork Core


Manages Plugins, Callbacks and Interfaces.

A plugin is a Python module providing a class `Plugin`.
Callbacks are all the methods provided by the class `Plugin` (with some
exceptions, like methods starting with `_`).
Interfaces are simply conventions: Plugins pretending to implement some
interfaces must implement the corresponding methods. No check is done to ensure
they do.


## Example


### Plugin

`openpaperwork\_plugin/\_\_init\_\_.py`

```py
import openpaperwork_core

class Plugin(openpaperwork_core.PluginBase):
    # indicates that users should be able to disable/enable this plugin in
    # the UI (if available/possible in the application)
    USER_VISIBLE = True

    def __init__(self):
        # do something, but the least possible
        # cannot rely on dependencies here.
        pass

    def get_implementated_interfaces(self):
        return ['interface_name_toto', 'interface_name_tutu']

    def get_deps(self):
        return {
            'plugins': [
                'module_name_a',
                'module_name_b',
            ],
            'interfaces': [
                'interface_name_a',
            ],
        }

    def init(self, core):
        # all the dependnecies have loaded and initialized.
        # we can safely rely on them here.
        pass

    def some_method_a(self, arg_a):
        # do something
```


### Application using the core

```py
import openpaperwork_core


core = openpaperwork_core.Core()

# load mandatory plugins
core.load("openpaperwork_plugin")

# load plugins requested by your user if any
core.load(...)

# init() will load dependencies and call method `init()` on all the plugins
core.init()

# call_all() will call all the methods with the specified name. Return values
# are ignored. You have to pass a callback as argument if you want to get
# result from all callbacks.
core.call_all('some_method_a', "random_argument")

# call_one() will call one of the methods with the specified name.
# It is assumed that only one callback has this name. Return value of the
# callback is returned as it.
return_value = core.call_one('some_method_a', "random_argument")
```