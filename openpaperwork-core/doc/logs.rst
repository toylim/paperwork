Log management plugins
======================

Log management plugins catch Python logs (see `logging`), format them and
send them somewhere.

`uncaught_exception`
---------------------

Broadcast uncaught exceptions (see `sys.excepthook`) by calling
`self.core.call_all("on_uncaught_exception", exc_info)`.


`logs.print`
------------

Send the logs to stderr, stdout or a file. It can send to many outputs at the
same time.

Configuration entries are as follow:

.. code-block:: ini

    [logging]
    level = str:info  # none, critical, error, warn, warning, info, debug
    files = str:stderr,temp,/tmp/test.txt  # 'stderr', 'temp', or a file path
    format = str:[%(levelname)-6s] [%(name)-30s] %(message)s

It monitors the configuration. So to change its settings, you can just update
the configuration using the plugin `openpaperwork_core.config`.

----

.. automodule:: openpaperwork_core.log_collector
   :members:
   :undoc-members:
