# OpenPaperwork Core

Manages Plugins, Callbacks and Interfaces.

## Basic concepts

The idea behind OpenPaperwork's plugins is similar to
[Python duck typing](https://en.wikipedia.org/wiki/Duck_typing): When you
request something, it does not matter who does the job as long as it's done. To
that end, plugins provide callbacks and any code that needs something done
calls them. They have no idea what plugins they are calling exactly and it
doesn't matter.

Calling code can call all the callbacks one with a given name on after the
other(`core.call_all()`) or just call them until one of them reply with a
value != `None` (`core.call_success()`).

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
    # callbacks will always be run before those of priority <= 21
    # but after those of priority >= 23
    PRIORITY = 22

    def __init__(self):
        # do something, but the least possible
        # cannot rely on dependencies here.
        pass

    def get_interfaces(self):
        return ['interface_name_toto', 'interface_name_tutu']

    def get_deps(self):
        return {
            'plugins': [
                # specify that some plugins are explicitely required
                # (not recommended)
                'module_name_a',
                'module_name_b',
            ],
            'interfaces': [
                # specify that we are looking for plugins implemented the
                # specified interface(s) (recommended). Provide also
                # some default plugins to load if no plugins provide the
                # requested interface yet. Core will try to load them one
                # after the other until the interface is available.
                ('interface_name_a', [
                    'suggested_default_plugin_a',
                    'suggested_default_plugin_b',
                ])
                ('interface_name_b', [
                    'suggested_default_plugin_d',
                    'suggested_default_plugin_e',
                ])
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


## Convention

### `call_success()`

Callbacks that are expected to be called with `call_success()` try to do their
job. If they can't, they return `None` hoping that another callback can
do the job.
