import logging
import sys
import threading
import traceback


LOGGER = logging.getLogger(__name__)


class BasePromise(object):
    def __init__(
                self, core, func=None, args=None, kwargs=None, parent=None,
                hide_catched_exceptions=False
            ):
        # we allow dummy Promise with not function provided. It allows to
        # write cleaner code in some cases.
        self.core = core
        self.func = func
        self.hide_catched_exceptions = hide_catched_exceptions
        if args is None:
            self.args = ()
        else:
            self.args = args
        if kwargs is None:
            self.kwargs = {}
        else:
            self.kwargs = kwargs
        self.parent = parent

        self._then = []
        self._catch = []

        self.parent_promise_return = None
        self.created_by = traceback.extract_stack()

    def __str__(self):
        return "Promise<{}>({})".format(str(self.func), id(self))

    def __repr__(self):
        return str(self)

    def then(self, callback, *args, **kwargs):
        if isinstance(callback, BasePromise):
            assert(args is None or len(args) <= 0)
            assert(kwargs is None or len(kwargs) <= 0)
            last_promise = callback
            while callback.parent is not None:
                callback = callback.parent
            next_promise = callback
            next_promise.parent = self
        else:
            next_promise = Promise(self.core, callback, args, kwargs, parent=self)
            last_promise = next_promise
        self._then.append(next_promise)
        return last_promise

    def catch(self, callback):
        self._catch.append(callback)
        return self

    def on_error(self, exc):
        if len(self._catch) > 0:
            if self.hide_catched_exceptions:
                trace = lambda *args, **kwargs: None
            else:
                trace = LOGGER.warning
            catched = "catched"
        elif len(self._then) > 0:
            for t in self._then:
                t.on_error(exc)
            return
        else:
            trace = LOGGER.error
            catched = "uncatched"

        trace("=== %s exception in promise ===", catched, exc_info=exc)
        trace("promise.func=%s", self.func)
        trace("promise.args=%s", self.args)
        trace("promise.kwargs=%s", self.kwargs)
        trace("promise.parent=%s", self.parent)
        trace(
            "promise.parent_promise_return=%s", self.parent_promise_return
        )
        trace("=== Promise was created by ===")
        for (idx, stack_el) in enumerate(self.created_by):
            trace(
                "%2d: %20s: L%5d: %s",
                idx, stack_el[0], stack_el[1], stack_el[2]
            )

        if len(self._catch) > 0:
            for c in self._catch:
                self.core.call_one("schedule", c, exc)
            return

        raise exc

    def schedule(self, *args):
        if self.parent is not None:
            self.parent.schedule(*args)
        else:
            if args == ():
                args = None
            self.core.call_one("schedule", self.do, args)

    def wait(self):
        assert(
            # must never be called from main loop.
            threading.current_thread().ident !=
            self.core.call_success("mainloop_get_thread_id")
        )
        event = threading.Event()
        out = [None]

        def wakeup(r=None):
            out[0] = r
            event.set()

        self.then(event.set)
        event.wait()
        return r[0]


class Promise(BasePromise):
    def do(self, parent_r=None):
        self.parent_promise_return = parent_r
        try:
            if self.func is None:
                our_r = None
            else:
                if parent_r is None:
                    args = self.args
                else:
                    args = (parent_r,) + self.args

                LOGGER.debug(
                    "Promise: Begin: %s(%s, %s)", self.func, args, self.kwargs
                )
                our_r = self.func(*args, **self.kwargs)
                LOGGER.debug(
                    "Promise: End: %s(%s, %s)", self.func, args, self.kwargs
                )

            for t in self._then:
                self.core.call_one("schedule", t.do, our_r)
        except Exception as exc:
            self.on_error(exc)


class ThreadedPromise(BasePromise):
    """
    Promise for which the provided callback will be run in another thread,
    leaving the main loop thread free to do other things.

    IMPORTANT: This should ONLY be used for long-lasting tasks that cannot
    be split in small tasks (image processing, OCR, etc). The callback provided
    must be really careful regarding thread-safety.
    """

    def _threaded_do(self, parent_r):
        try:
            if parent_r is None:
                args = self.args
            else:
                args = (parent_r,) + self.args

            LOGGER.debug(
                "Threaded promise: Begin: %s(%s, %s)",
                self.func, args, self.kwargs
            )
            our_r = self.func(*args, **self.kwargs)
            LOGGER.debug(
                "Threaded promise: end: %s(%s, %s)",
                self.func, args, self.kwargs
            )

            for t in self._then:
                self.core.call_one("schedule", t.do, our_r)
        except Exception as exc:
            self.on_error(exc)
        finally:
            self.core.call_all("mainloop_unref", self)

    def do(self, parent_r=None):
        self.parent_promise_return = parent_r
        try:
            if self.func is None:
                # no thread, we immediately schedule the next promises
                for t in self._then:
                    self.core.call_one("schedule", t.do, None)
                return

            thread = threading.Thread(
                target=self._threaded_do, args=(parent_r,)
            )

            # The mainloop doesn't track other threads, but if there is
            # a graceful shutdown waiting, we don't want it to stop the main
            # loop before our thread is done.
            # --> increment mainloop ref counter before
            self.core.call_all("mainloop_ref", self)

            thread.start()
        except Exception as exc:
            self.on_error(exc)
            return
