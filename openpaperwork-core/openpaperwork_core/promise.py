import logging
import sys
import threading
import traceback


LOGGER = logging.getLogger(__name__)


class BasePromise(object):
    def __init__(self, core, func=None, args=None, kwargs=None, parent=None):
        # we allow dummy Promise with not function provided. It allows to
        # write cleaner code in some cases.
        self.core = core
        self.func = func
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
            for c in self._catch:
                self.core.call_one("schedule", c, exc)
        elif len(self._then) > 0:
            for t in self._then:
                t.on_error(exc)
        else:
            LOGGER.error(
                "=== Uncatched exception in promise ===", exc_info=exc
            )
            LOGGER.error("promise.func=%s", self.func)
            LOGGER.error("promise.args=%s", self.args)
            LOGGER.error("promise.kwargs=%s", self.kwargs)
            LOGGER.error("promise.parent=%s", self.parent)
            LOGGER.error(
                "promise.parent_promise_return=%s", self.parent_promise_return
            )
            LOGGER.error("=== Promise was created by ===")
            for (idx, stack_el) in enumerate(self.created_by):
                LOGGER.error(
                    "%2d: %20s: L%5d: %s",
                    idx, stack_el[0], stack_el[1], stack_el[2]
                )
            raise exc

    def schedule(self, *args):
        if self.parent is not None:
            self.parent.schedule(*args)
        else:
            if args == ():
                args = None
            self.core.call_one("schedule", self.do, args)


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
            return


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
            return

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
            thread.start()
        except Exception as exc:
            self.on_error(exc)
            return
