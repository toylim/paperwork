import threading

from .. import PluginBase


class Run(threading.Thread):
    def __init__(self, core, func, args, kwargs):
        super().__init__()
        self.core = core
        self.func = func
        self.args = args
        self.kwargs = kwargs

        # The mainloop can't track other threads, but if there is
        # a graceful shutdown waiting, we don't want it to stop the main
        # loop before our thread is done.
        # --> increment mainloop ref counter before
        core.call_all("mainloop_ref", self)

    def run(self):
        self.func(*self.args, **self.kwargs)
        self.core.call_all("mainloop_unref", self)


class Plugin(PluginBase):
    """
    Simply create a thread for each task to run. Less efficient than a thread
    pool, but may be useful for testing or debugging.
    """
    def get_interfaces(self):
        return ['thread']

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def thread_start(self, func, *args, **kwargs):
        Run(self.core, func, args, kwargs).start()
        return True
