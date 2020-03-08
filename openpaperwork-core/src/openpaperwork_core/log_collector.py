import datetime
import faulthandler
import logging
import sys
import tempfile

from . import PluginBase


LOGGER = logging.getLogger(__name__)


g_tmp_file = None


def _get_tmp_file():
    global g_tmp_file

    if g_tmp_file is not None:
        return g_tmp_file

    date = datetime.datetime.now()
    date = date.strftime("%Y%m%d_%H%M_%S")
    t = tempfile.NamedTemporaryFile(
        mode='w',
        suffix=".txt",
        prefix="openpaperwork_{}_".format(date),
        encoding='utf-8'
    )
    if sys.stderr is not None:
        sys.stderr.write("Temporary file = {}\n".format(t.name))
    g_tmp_file = t
    return t


class _LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        logging.getLogger().setLevel(logging.DEBUG)
        self.formatter = logging.Formatter(Plugin.DEFAULT_LOG_FORMAT)
        self.out_fds = {sys.stdout}
        sys.excepthook = self.on_uncatched_exception_cb

    def emit(self, record):
        if self.formatter is None:
            return
        line = self.formatter.format(record)
        for fd in self.out_fds:
            fd.write(line + "\n")

    def on_uncatched_exception_cb(self, exc_type, exc_value, exc_tb):
        LOGGER.error(
            "=== UNCATCHED EXCEPTION ===",
            exc_info=(exc_type, exc_value, exc_tb)
        )
        LOGGER.error("===========================")


class Plugin(PluginBase):
    CONFIG_FILE_SEPARATOR = ","

    DEFAULT_LOG_LEVEL = 'info'
    DEFAULT_LOG_FILES = 'temp' + CONFIG_FILE_SEPARATOR + 'stdout'
    DEFAULT_LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s'

    LOG_LEVELS = {
        'none': logging.CRITICAL,
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARN,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
    }
    SPECIAL_FILES = {
        'stdout': lambda: sys.stdout,
        'stderr': lambda: sys.stderr,
        'temp': _get_tmp_file,
    }

    def __init__(self):
        self.core = None
        self.log_file_paths = set()
        self.log_handler = None

    def get_interfaces(self):
        return []

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def init(self, core):
        self.core = core

        self.log_handler = _LogHandler()
        logging.getLogger().addHandler(self.log_handler)

        s = core.call_success(
            "config_build_simple", "logging", "level",
            lambda: self.DEFAULT_LOG_LEVEL
        )
        core.call_all("config_register", "log_level", s)
        core.call_all('config_add_observer', "log_level", self._reload_config)

        s = core.call_success(
            "config_build_simple", "logging", "files",
            lambda: self.DEFAULT_LOG_FILES
        )
        core.call_all("config_register", "log_files", s)
        core.call_all('config_add_observer', "log_files", self._reload_config)

        s = core.call_success(
            "config_build_simple", "logging", "format",
            lambda: self.DEFAULT_LOG_FORMAT
        )
        core.call_all("config_register", "log_format", s)
        core.call_all('config_add_observer', "log_format", self._reload_config)

        self._reload_config()

    def _disable_logging(self):
        for fd in self.log_handler.out_fds:
            if fd != sys.stdout and fd != sys.stderr and fd != g_tmp_file:
                fd.close()
        self.log_handler.out_fds = {sys.stdout}

    def _enable_logging(self):
        self.log_handler.out_fds = set()
        first = None
        for file_path in self.log_file_paths:
            if sys.stderr is not None:  # if app is not frozen
                sys.stderr.write("Writing logs to {}\n".format(file_path))
            if file_path.lower() not in self.SPECIAL_FILES:
                fd = open(file_path, 'a')
                self.log_handler.out_fds.add(fd)
            else:
                fd = self.SPECIAL_FILES[file_path.lower()]()
                self.log_handler.out_fds.add(fd)
            if first is None:
                first = fd
        faulthandler.enable(file=first)

    def _reload_config(self, *args, **kwargs):
        LOGGER.info("Reloading logging configuration")
        self._disable_logging()
        try:
            log_level = self.core.call_success('config_get', "log_level")
            if sys.stderr is not None:  # if app is not frozen
                sys.stderr.write("Log level: {}\n".format(log_level))
            logging.getLogger().setLevel(self.LOG_LEVELS[log_level])
            self.log_file_paths = self.core.call_success(
                'config_get', "log_files",
            ).split(self.CONFIG_FILE_SEPARATOR)
            self.log_handler.formatter = logging.Formatter(
                self.core.call_success('config_get', "log_format")
            )
        finally:
            self._enable_logging()
