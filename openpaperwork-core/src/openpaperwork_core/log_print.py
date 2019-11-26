"""
Minimalist log handling. Print everything to stdout by default
"""

import datetime
import logging
import sys

from . import PluginBase


LOGGER = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s\n'

    def __init__(self):
        super().__init__()
        self.formatter = logging.Formatter(self.LOG_FORMAT)
        self.out_fd = sys.stdout
        sys.excepthook = self.on_uncatched_exception_cb

    def emit(self, record):
        line = self.formatter.format(record)
        self.out_fd.write(line)

    def on_uncatched_exception_cb(self, exc_type, exc_value, exc_tb):
        LOGGER.error(
            "=== UNCATCHED EXCEPTION ===",
            exc_info=(exc_type, exc_value, exc_tb)
        )
        LOGGER.error("===========================")


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.log_handler = LogHandler()
        logging.getLogger().addHandler(self.log_handler)

    def get_interfaces(self):
        return []

    def set_log_output(self, fd):
        self.log_handler.out_fd = fd

    def set_log_level(self, level):
        LOG_LEVELS = {
            'none': logging.CRITICAL,
            'critical': logging.CRITICAL,
            'error': logging.ERROR,
            'warn': logging.WARN,
            'warning': logging.WARNING,
            'info': logging.INFO,
            'debug': logging.DEBUG,
        }
        logging.getLogger().setLevel(LOG_LEVELS[level.lower()])
