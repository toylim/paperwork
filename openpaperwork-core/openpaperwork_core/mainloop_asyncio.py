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
        self.task_count = 0

    def _check_mainloop_instantiated(self):
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
            self.task_count = 0

    def get_interfaces(self):
        return [
            "mainloop",
        ]

    def mainloop(self, halt_on_uncatched_exception=True):
        self._check_mainloop_instantiated()
        self.halt_on_uncatched_exception = halt_on_uncatched_exception
        self.loop.run_forever()
        if self.halt_cause is not None:
            LOGGER.error("Main loop stopped because %s", str(self.halt_cause))
            raise self.halt_cause

    def mainloop_quit_graceful(self):
        self.schedule(self._mainloop_quit_graceful)

    def _mainloop_quit_graceful(self):
        if self.task_count > 1:
            LOGGER.info("Quit graceful: Remaining tasks: %d", self.task_count)
            self.schedule(self.mainloop_quit_graceful, delay_s=0.2)
            return

        LOGGER.info("Quit graceful: Quitting")
        self.mainloop_quit_now()

    def mainloop_quit_now(self):
        self.loop.stop()
        self.loop = None
        self.task_count = 0

    def mainloop_ref(self, obj):
        self.task_count += 1

    def mainloop_unref(self, obj):
        self.task_count -= 1

    def schedule(self, func, *args, delay_s=0, **kwargs):
        assert(hasattr(func, '__call__'))

        self._check_mainloop_instantiated()

        self.task_count += 1

        async def decorator(args, kwargs):
            try:
                func(*args, **kwargs)
                self.task_count -= 1
            except Exception as exc:
                if self.halt_on_uncatched_exception:
                    LOGGER.error(
                        "Main loop: Uncatched exception ! Quitting",
                        exc_info=exc
                    )
                    self.halt_cause = exc
                    self.mainloop_quit_now()
                else:
                    LOGGER.error(
                        "Main loop: Uncatched exception !", exc_info=exc
                    )

        coroutine = decorator(args, kwargs)

        args = (self.loop.create_task, coroutine)
        if delay_s != 0:
            args = (self.loop.call_later, delay_s) + args
        self.loop.call_soon_threadsafe(args[0], *(args[1:]))
