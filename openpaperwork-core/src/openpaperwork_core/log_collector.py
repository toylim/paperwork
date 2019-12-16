import datetime
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
        self.out_fds = {sys.stderr}
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
    DEFAULT_LOG_FILES = 'stderr' + CONFIG_FILE_SEPARATOR + 'temp'
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
        'stderr': lambda: open("/dev/stderr", "w"),
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
            if fd != sys.stderr and fd != g_tmp_file:
                fd.close()
        self.log_handler.out_fds = {sys.stderr}

    def _enable_logging(self):
        self.log_handler.out_fds = set()
        for file_path in self.log_file_paths:
            if sys.stderr is not None:  # if app is frozen
                sys.stderr.write("Writing logs to {}\n".format(file_path))
            if file_path.lower() not in self.SPECIAL_FILES:
                self.log_handler.out_fds.add(open(file_path, 'a'))
            else:
                self.log_handler.out_fds.add(
                    self.SPECIAL_FILES[file_path.lower()]()
                )

    def _reload_config(self, *args, **kwargs):
        self._disable_logging()
        try:
            log_level = self.core.call_success('config_get', "log_level")
            logging.getLogger().setLevel(self.LOG_LEVELS[log_level])
            self.log_file_paths = self.core.call_success(
                'config_get', "log_files",
            ).split(self.CONFIG_FILE_SEPARATOR)
            self.log_handler.formatter = logging.Formatter(
                self.core.call_success('config_get', "log_format")
            )
        finally:
            self._enable_logging()
