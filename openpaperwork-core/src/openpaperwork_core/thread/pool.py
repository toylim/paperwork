import logging
import multiprocessing
import queue
import threading

from . import Task
from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Thread(threading.Thread):
    def __init__(self, plugin, thread_id):
        super().__init__(name="paperwork_thread_{}".format(thread_id))
        self.daemon = True
        self.plugin = plugin
        self.core = plugin.core
        self.running = True

    def run(self):
        LOGGER.info("Thread %s ready", self.name)
        while True:
            task = self.plugin.queue.get()
            if task is None:
                break
            task.do()
        LOGGER.info("Thread %s stopped", self.name)


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()

    def get_interfaces(self):
        return ['thread']

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.pool = [
            Thread(self, x)
            for x in range(0, multiprocessing.cpu_count())
        ]

    def on_mainloop_start(self):
        for t in self.pool:
            t.start()

    def on_mainloop_quit(self):
        for t in self.pool:
            self.queue.put(None)

    def thread_start(self, func, *args, **kwargs):
        task = Task(self.core, func, args, kwargs)
        self.queue.put(task)
