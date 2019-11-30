import asyncio
import logging
import threading

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    A main loop based on asyncio. Not as complete as GLib main loop, but
    good enough for shell commands.
    """
    def __init__(self):
        super().__init__()
        self.halt_on_uncatched_exception = True
        self.loop = None
        self.loop_ident = None
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
        """
        Wait for callbacks to be scheduled and execute them.

        This method is blocking and will block until `mainloop_quit*()` is
        called.
        """
        self._check_mainloop_instantiated()
        self.halt_on_uncatched_exception = halt_on_uncatched_exception

        self.loop_ident = threading.current_thread().ident
        try:
            self.loop.run_forever()
        finally:
            self.loop_ident = None
        if self.halt_cause is not None:
            LOGGER.error("Main loop stopped because %s", str(self.halt_cause))
            raise self.halt_cause

    def mainloop_get_thread_id(self):
        """
        Gets the ID of the thread running the main loop. `None` if no
        thread is running it.
        """
        return self.loop_ident

    def mainloop_quit_graceful(self):
        """
        Wait for all the scheduled callbacks to be executed and then stops
        the main loop.
        """
        self.schedule(self._mainloop_quit_graceful)

    def _mainloop_quit_graceful(self):
        if self.task_count > 1:  # keep in mind this function is in a task too
            LOGGER.info(
                "Quit graceful: Remaining tasks: %d", self.task_count - 1
            )
            self.schedule(self.mainloop_quit_graceful, delay_s=0.2)
            return

        LOGGER.info("Quit graceful: Quitting")
        self.mainloop_quit_now()

    def mainloop_quit_now(self):
        """
        Stops the main loop right now.

        Note that it cannot interrupt a callback being executed, but no
        callback scheduled after this one will be executed.
        """
        self.loop.stop()
        self.loop = None
        self.task_count = 0

    def mainloop_ref(self, obj):
        """
        If you run a task independently from the main loop, you may want
        to increment the reference counter of the main loop so
        `mainloop_quit_graceful` does not interrupt the main loop while your
        task is still running.

        ThreadedPromise already takes care of incrementing and decrementing
        this reference counter.
        """
        self.task_count += 1

    def mainloop_unref(self, obj):
        self.task_count -= 1

    def schedule(self, func, *args, delay_s=0, **kwargs):
        """
        Request that the main loop executes the callback `func`.
        Will return immediately.
        """
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
                        "Main loop: Uncatched exception (%s) ! Quitting",
                        func, exc_info=exc
                    )
                    self.halt_cause = exc
                    self.mainloop_quit_now()
                else:
                    LOGGER.error(
                        "Main loop: Uncatched exception (%s) !",
                        func, exc_info=exc
                    )

        coroutine = decorator(args, kwargs)

        args = (self.loop.create_task, coroutine)
        if delay_s != 0:
            args = (self.loop.call_later, delay_s) + args
        self.loop.call_soon_threadsafe(args[0], *(args[1:]))

    def mainloop_execute(self, func, *args, **kwargs):
        """
        Ensure a function is run on the main loop, even if called from
        a thread. Will return only once the callback `func` has been
        executed. Will return the value returned by `func`.

        This method makes it easier to work with non-thread-safe modules
        (sqlite3 for instance).
        """
        current = threading.current_thread().ident

        # XXX(Jflesch):
        # if self.loop_ident is None, it means the mainloop hasn't been started
        # yet --> we cannot run the function on the mainloop anyway, so
        # we assume we are on the same thread that will later run the main
        # loop.
        if self.loop_ident is None or current == self.loop_ident:
            return func(*args, **kwargs)

        event = threading.Event()
        out = [None]
        exc = [None]

        def get_result():
            try:
                out[0] = func(*args, **kwargs)
            except Exception as e:
                exc[0] = e
            event.set()

        self.schedule(get_result)
        event.wait()

        if exc[0] is not None:
            raise exc[0]
        return out[0]
