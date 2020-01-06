import logging

import pympler.tracker

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def __init__(self):
        self.tracker = None

    def get_interfaces(self):
        return ['memleak_detector']

    def on_memleak_track_start(self):
        LOGGER.info("Starting memory leaks tracking ...")
        self.tracker = pympler.tracker.SummaryTracker()

    def on_memleak_track_stop(self):
        if self.tracker is not None:
            LOGGER.info("Stopping memory leaks tracking ...")
            self.tracker.print_diff()
        self.tracker = None
