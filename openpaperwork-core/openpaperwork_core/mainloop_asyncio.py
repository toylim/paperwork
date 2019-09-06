import asyncio
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    A main loop. Not as good as GLib main loop, but good enough for shell
    commands.
    """
    def __init__(self):
        super().__init__()
        self.halt_on_uncatched_exception = True
        self.loop = None
        self.halt_cause = None

    def _chk_mainloop(self):
        if self.loop is None:
            self.loop = asyncio.get_event_loop()

    def get_interfaces(self):
        return [
            "mainloop",
        ]

    def mainloop(self, halt_on_uncatched_exception=True):
        self._chk_mainloop()
        self.halt_on_uncatched_exception = halt_on_uncatched_exception
        self.loop.run_forever()
        if self.halt_cause is not None:
            LOGGER.error("Main loop stopped because %s", str(self.halt_cause))

    def mainloop_quit(self):
        self.loop.stop()
        self.loop = None

    def schedule(self, func, *args, **kwargs):
        assert(hasattr(func, '__call__'))

        self._chk_mainloop()

        def decorator(_args):
            # event_loop.call_soon() do not accept kwargs (just args),
            # so we have to do some wrapping.
            try:
                func(*args, **kwargs)
            except Exception as exc:
                LOGGER.error("Main loop: Uncatched exception !", exc_info=exc)
                if self.halt_on_uncatched_exception:
                    self.halt_cause = exc
                    self.mainloop_quit()

        self.loop.call_soon_threadsafe(decorator, (args, kwargs))
