import logging
import threading

try:
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False


import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    A main loop based on GLib's mainloop.
    See `openpaperwork_core.mainloop.asyncio` for doc.
    """
    def __init__(self):
        super().__init__()
        self.halt_on_uncatched_exception = True
        self.loop = None
        self.loop_ident = None
        self.halt_cause = None
        self.task_count = 0

    def get_interfaces(self):
        return [
            "chkdeps",
            "mainloop",
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['gi.repository.GLib']['debian'] = 'gir1.2-glib-2.0'
            out['gi.repository.GLib']['ubuntu'] = 'gir1.2-glib-2.0'

    def _check_mainloop_instantiated(self):
        if self.loop is None:
            self.loop = GLib.MainLoop.new(None, False)  # !running

    def mainloop(self, halt_on_uncatched_exception=True):
        self._check_mainloop_instantiated()
        self.halt_on_uncatched_exception = halt_on_uncatched_exception

        self.loop_ident = threading.current_thread().ident

        try:
            self.loop.run()
        finally:
            self.loop_ident = None

        if self.halt_cause is not None:
            halt_cause = self.halt_cause
            self.halt_cause = None
            LOGGER.error("Main loop stopped because %s", str(self.halt_cause))
            raise halt_cause

    def mainloop_get_thread_id(self):
        return self.loop_ident

    def mainloop_quit_graceful(self):
        self.mainloop_schedule(self._mainloop_quit_graceful)

    def _mainloop_quit_graceful(self):
        if self.task_count > 1:  # keep in mind this function is in a task too
            LOGGER.info(
                "Quit graceful: Remaining tasks: %d", self.task_count - 1
            )
            self.mainloop_schedule(self.mainloop_quit_graceful, delay_s=0.2)
            return

        LOGGER.info("Quit graceful: Quitting")
        self.mainloop_quit_now()
        self.task_count = 1  # we are actually the one task still running

    def mainloop_quit_now(self):
        self.loop.quit()
        self.loop = None
        self.task_count = 0

    def mainloop_ref(self, obj):
        self.task_count += 1

    def mainloop_unref(self, obj):
        self.task_count -= 1
        assert(self.task_count >= 0)

    def mainloop_schedule(self, func, *args, delay_s=0, **kwargs):
        assert(hasattr(func, '__call__'))

        self._check_mainloop_instantiated()

        self.task_count += 1

        def decorator(func, args):
            (args, kwargs) = args
            try:
                func(*args, **kwargs)
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
            finally:
                self.task_count -= 1
            return False

        args = (args, kwargs)

        if delay_s is None:
            GLib.idle_add(decorator, func, args)
        else:
            GLib.timeout_add(delay_s * 1000, decorator, func, args)

    def mainloop_execute(self, func, *args, **kwargs):
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

        self.mainloop_schedule(get_result)
        event.wait()

        if exc[0] is not None:
            raise exc[0]
        return out[0]
