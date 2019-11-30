Configuration management plugin
===============================

Configuration management plugins provide a way to store an application
configuration. Openpaperwork_core provides the plugin
`openpaperwork_core.config_file` that stores the configuration in a
configuration file (see Python's `configparser`).

There could be other plugins providing identical API and interface that store
the configuration in Windows registry or in an Android ContentProvider. However
since they are not cross-platform, they would have to be distributed in
separated packages.


.. automodule:: openpaperwork_core.config_file
   :members:
   :undoc-members:
