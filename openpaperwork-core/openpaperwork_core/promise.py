import logging


LOGGER = logging.getLogger(__name__)


class Promise(object):
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

    def __str__(self):
        return "Promise<{}>({})".format(str(self.func), id(self))

    def __repr__(self):
        return str(self)

    def then(self, callback, *args, **kwargs):
        if isinstance(callback, Promise):
            assert(args is None or len(args) <= 0)
            assert(kwargs is None or len(kwargs) <= 0)
            while callback.parent is not None:
                callback = callback.parent
            promise = callback
            promise.parent = self
        else:
            promise = Promise(self.core, callback, args, kwargs, parent=self)
        self._then.append(promise)
        return promise

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
            raise

    def do(self, r=None):
        try:
            if self.func is not None:
                if r is not None:
                    args = (r,) + self.args
                else:
                    args = self.args
                r = self.func(*args, **self.kwargs)

            for t in self._then:
                self.core.call_one("schedule", t.do, r)
        except Exception as exc:
            self.on_error(exc)
            return

    def schedule(self):
        if self.parent is not None:
            self.parent.schedule()
        else:
            self.core.call_one("schedule", self.do)
