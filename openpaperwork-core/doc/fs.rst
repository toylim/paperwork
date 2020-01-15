File system plugins
===================

Those plugins provide methods to access files on various storages. For
instance, 'python' plugin uses the python API to access local files
(`file://`), so does the GIO implementation (openpaperwork-gtk).
Memory plugin allow storing data in filesystem-like manner (`memory://`).
Later other plugins could provide access to other storages (MariaDB, HTTP,
etc).

The reference implementation is 'python'.

A fake/mock implementation is provided for testing. It behaves in a way
similar to the memory plugin.

----

Python-based implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: openpaperwork_gtk.fs.python
   :members:
   :undoc-members:

----

In-Memory implementation
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: openpaperwork_core.fs.memory
   :members:
   :undoc-members:
