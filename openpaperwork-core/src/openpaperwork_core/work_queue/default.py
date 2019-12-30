import collections
import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class WorkQueue(object):
    def __init__(self, name):
        self.name = name
        self.queue = collections.deque()
        self.running = False

    def add_promise(self, promise):
        self.queue.append(promise)

        if not self.running:
            self._run_next_promise()

    def _run_next_promise(self, *args, **kwargs):
        try:
            self.running = True
            promise = self.queue.popleft()
            promise = promise.then(self._run_next_promise)
            promise.schedule()
        except IndexError:
            self.running = False
            return

    def cancel(self, promise):
        try:
            self.queue.remove(promise)
        except ValueError:
            LOGGER.debug(
                "Cannot cancel promise [%s]. (already running ?)", promise
            )

    def cancel_all(self):
        # reset the queue
        self.queue = collections.deque()


class Plugin(PluginBase):
    def __init__(self):
        self.queues = {}

    def get_interfaces(self):
        return ['work_queue']

    def get_deps(self):
        return [
            {
               'interface': 'mainloop',
               'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def work_queue_create(self, queue_name):
        LOGGER.debug("Creating work queue [%s]", queue_name)
        self.queues[queue_name] = WorkQueue(queue_name)
        return True

    def work_queue_add_promise(self, queue_name, promise):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].add_promise(promise)
        return True

    def work_queue_cancel(self, queue_name, promise):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].cancel(promise)
        return True

    def work_queue_cancel_all(self, queue_name):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].cancel_all()
        return True
