Plugin Example
==============


.. code-block:: python

   import openpaperwork_core

   class Plugin(openpaperwork_core.PluginBase):
       # callbacks will always be run before those of priority <= 21
       # but after those of priority >= 23
       PRIORITY = 22

       def __init__(self):
           # do something, but the least possible
           # cannot rely on any dependencies here.
           pass

       def get_interfaces(self):
           return ['interface_name_toto', 'interface_name_tutu']

       def get_deps(self):
           # specify that we are looking for plugins implementing the
           # specified interface(s) (recommended).
           # Provide also some default plugins to load if no plugins provide the
           # requested interface yet.
           # By default, it is assumed that the specified interface has already
           # be loaded (default plugin list must be exhaustive). If not, an error
           # will be raised.
           # When running tests, the default plugin list is used (it allows to
           # make sure it is exhaustive).
           # Note that plugins may be loaded in any order. Dependencies may not
           # be satisfied yet when they are loaded.
           # When initializing plugins, the core will make sure that dependencies
           # are satisfied, loaded and initialized before calling `init()`.
           return [
               {
                   'interface': 'interface_name_a',
                   'defaults': [
                       'suggested_default_plugin_a',
                       'suggested_default_plugin_b',
                   ],
               },
               {
                   'interface': 'inteface_name_b',
                   'defaults': [
                       'suggested_default_plugin_d',
                       'suggested_default_plugin_e',

                       # do not raise an error if no plugin already-loaded
                       # implements the required interface. Instead, load the
                       # default plugins.
                       'expected_already_satisfied': False,
                   ],
               }
           ]

       def init(self, core):
           # all the dependencies have loaded and initialized.
           # we can safely rely on them here.
           pass

       def some_method_a(self, arg_a):
           # do something
