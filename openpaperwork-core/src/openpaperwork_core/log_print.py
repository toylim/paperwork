"""
Minimalist log handling. Print everything to stdout by default
"""

import datetime
import logging
import os
import sys

from . import PluginBase


LOGGER = logging.getLogger(__name__)

LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s\n'

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;{}m"
BOLD_SEQ = "\033[1m"

COLORS = {
    'CRITICAL': 31,
    'ERROR': 31,
    'WARNING': 33,
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname
        if levelname in COLORS:
            levelname = (
                COLOR_SEQ.format(COLORS[levelname])
                + levelname + RESET_SEQ
            )
            record.levelname = levelname
        return logging.Formatter.format(self, record)


class LogHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self._set_out_fd(sys.stdout)
        sys.excepthook = self.on_uncatched_exception_cb

    def emit(self, record):
        line = self.formatter.format(record)
        self._out_fd.write(line)

    def _get_out_fd(self):
        return self._out_fd

    def _set_out_fd(self, fd):
        isatty = False
        if hasattr(fd, 'fileno'):
            isatty = os.isatty(fd.fileno())
        if isatty:
            self.formatter = ColorFormatter(LOG_FORMAT)
        else:
            self.formatter = logging.Formatter(LOG_FORMAT)
        self._out_fd = fd

    out_fd = property(_get_out_fd, _set_out_fd)

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
