Log management plugins
======================

Log management plugins catch Python logs (see `logging`), format them and
send them somewhere.


`log_print`
-----------

Send the logs to a file descriptor. The default file descriptor is
`sys.stderr`. Logging is configured through plugin callbacks.


----

.. automodule:: openpaperwork_core.log_print
   :members:
   :undoc-members:


`log_collector`
---------------

Send the logs to stderr, stdout or a file. It can send to many outputs at the
same time.

Configuration entries are as follow:

.. code-block:: ini

    [logging]
    level = str:info  # none, critical, error, warn, warning, info, debug
    files = str:stderr,temp,/tmp/test.txt  # 'stderr', 'temp', or a file path
    format = str:[%(levelname)-6s] [%(name)-30s] %(message)s

It monitors the configuration. So to change its settings, you can just update
the configuration using the plugin `openpaperwork_core.config_file`.

----

.. automodule:: openpaperwork_core.log_collector
   :members:
   :undoc-members:
