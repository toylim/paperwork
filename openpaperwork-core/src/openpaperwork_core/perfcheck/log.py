import logging
import threading
import time

from .. import PluginBase


LOGGER = logging.getLogger(__name__)

MIN_TIME_MS = 200


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.pending = {}

    def get_interfaces(self):
        return ['perfcheck']

    def on_perfcheck_start(self, task_name):
        k = (task_name, threading.get_ident())
        self.pending[k] = time.time()

    def on_perfcheck_stop(self, task_name, **extras):
        stop = time.time()
        k = (task_name, threading.get_ident())
        start = self.pending.pop(k)
        if (stop - start) * 1000 >= MIN_TIME_MS:
            LOGGER.warning(
                "Task '%s' took %dms (> %dms) ! (%s)",
                task_name, (stop - start) * 1000, MIN_TIME_MS, extras
            )
