Configuration plugin
====================

Configuration management plugins provide a way to store an application
configuration. Openpaperwork_core provides the plugin
`openpaperwork_core.config` that acts a frontend for backend plugins
(`openpaperowkr_core.config.backend.*`). It provides some high level
operations (like registering options and their default value). Other plugins
and applications should use this frontend only.

When initialized, plugins are expected to register any setting they need. Only
the plugin responsible for a setting register it ; Plugins depending on
settings registered by one of their dependency do not need to register them.

Backends provide access to the configuration storage (Python's ConfigParser,
Windows registry, Android Content Provider, etc). Reference implementation
for backends is `openpaperwork_core.config.backend.configparser` (based on
Python's ConfigParser).

----

Frontend plugin
~~~~~~~~~~~~~~~

.. automodule:: openpaperwork_core.config
   :members:
   :undoc-members:

----

Backend plugin: File
~~~~~~~~~~~~~~~~~~~~

.. automodule:: openpaperwork_core.config.backend.configparser
   :members:
   :undoc-members:
