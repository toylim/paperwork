import logging
import heapq
import traceback

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Task(object):
    def __init__(self, priority, insert_number, promise):
        self.priority = priority
        self.insert_number = insert_number
        self.promise = promise
        self.active = True
        self.created_by = traceback.extract_stack()

    def _on_error(self, exc):
        LOGGER.error("=== Promise was queued by ===")
        for (idx, stack_el) in enumerate(self.created_by):
            LOGGER.error(
                "%2d: %20s: L%5d: %s",
                idx, stack_el[0], stack_el[1], stack_el[2]
            )
        raise exc

    def __lt__(self, o):
        if self.priority < o.priority:
            return True
        if self.priority > o.priority:
            return False

        if self.insert_number < o.insert_number:
            return True

        return False


class WorkQueue(object):
    def __init__(self, name):
        self.insert_number = 0

        self.name = name
        self.queue = []
        self.all_tasks = {}
        self.running = False

    def add_promise(self, promise, priority=0):
        self.insert_number += 1

        task = Task(-1 * priority, self.insert_number, promise)

        heapq.heappush(self.queue, task)
        self.all_tasks[promise] = task

        if not self.running:
            self._run_next_promise()

    def _run_next_promise(self, *args, **kwargs):
        self.running = True

        try:
            task = None
            while task is None or not task.active:
                task = heapq.heappop(self.queue)
                self.all_tasks.pop(task.promise)
        except IndexError:
            self.running = False
            return

        promise = task.promise.then(self._run_next_promise)
        promise.catch(task._on_error)
        promise.schedule()

    def cancel(self, promise):
        try:
            task = self.all_tasks[promise]
            task.active = False
        except KeyError:
            LOGGER.debug(
                "Cannot cancel promise [%s]. (already running ?)", promise
            )

    def cancel_all(self):
        # reset the queue
        self.queue = []
        self.all_tasks = {}


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

    def work_queue_add_promise(self, queue_name, promise, priority=0):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].add_promise(promise, priority)
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
