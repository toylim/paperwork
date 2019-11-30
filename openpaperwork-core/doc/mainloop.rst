Mainloop plugins
================

Most GUI applications need a main loop. A main loop is a thread dedicated
to running callbacks provided by other threads (or stacked before the main loop
is started).

Depending on the environment in which you're working, you may need different
mainloop implementations. For instance, Python 3 provide main loop support
through `asyncio`. If you're working in a GTK environment, you will have to
use the GLib mainloop instead. Openpaperwork_core provides an implementation
that uses Python 3's `asyncio` module.

More advanced main loops may provide features such as waiting for an event to
occur on a file descriptor. The main loop interface provided here is kept
simple so it can easily be implemented for any other platforms.


.. automodule:: openpaperwork_core.mainloop_asyncio
   :members:
   :undoc-members:
