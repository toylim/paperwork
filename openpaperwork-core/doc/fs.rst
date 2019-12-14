File system plugins
===================

Those plugins provide methods to access files on various storages. For
instance, GIO plugin uses Gnome GLib to access local files (`file://`).
Memory plugin allow storing data in filesystem-like manner (`memory://`).
Later other plugins could provide access to other storages (MariaDB, HTTP,
etc).

The reference implementation is GIO.

A fake/mock implementation is provided for testing. It behaves in a way
similar to the memory plugin.

----

GIO
~~~

.. automodule:: openpaperwork_gtk.fs.gio
   :members:
   :undoc-members:

----

Memory
~~~~~~

.. automodule:: openpaperwork_core.fs.memory
   :members:
   :undoc-members:
