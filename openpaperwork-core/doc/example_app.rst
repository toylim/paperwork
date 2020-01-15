Calling Code Example
====================

.. code-block:: python

   import openpaperwork_core


   core = openpaperwork_core.Core()

   # Load mandatory plugins
   core.load("openpaperwork_plugin_a")
   core.load("mandatory_plugin_a")
   core.load("mandatory_plugin_b")

   # `init()` will load dependencies and call method `init()` on all the plugins
   # You can safely call `core.init()` many times
   core.init()

   # Load plugins requested by your user if any.
   # You can used previously loaded to get the plugin to load if you want.
   # For instance, you can load and initialize `openpaperwork_core.config`
   # and then use it to get a plugin list from a configuration file.
   core.load(...)

   core.init()

   nb_called = core.call_all('some_method_a', "random_argument")
   assert(nb_called > 0)

   return_value = core.call_success('some_method_a', "random_argument")
   assert(return_value is not None)
