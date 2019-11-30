import datetime
import logging
import sys
import tempfile

from . import PluginBase


LOGGER = logging.getLogger(__name__)


def _get_tmp_file():
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
    return t


class _LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.formatter = None
        self.out_fds = set()
        sys.excepthook = self.on_uncatched_exception_cb

    def emit(self, record):
        if self.formatter is None:
            return
        line = self.formatter.format(record)
        for fd in self.out_fds:
            fd.write(line)

    def on_uncatched_exception_cb(self, exc_type, exc_value, exc_tb):
        LOGGER.error(
            "=== UNCATCHED EXCEPTION ===",
            exc_info=(exc_type, exc_value, exc_tb)
        )
        LOGGER.error("===========================")


class Plugin(PluginBase):
    CONFIG_SECTION = 'logging'
    CONFIG_LOG_LEVEL = 'level'
    CONFIG_LOG_FILES = 'files'
    CONFIG_LOG_FORMAT = 'format'

    CONFIG_FILE_SEPARATOR = ","

    LOG_LEVELS = {
        'none': logging.CRITICAL,
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARN,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
    }
    DEFAULT_LOG_LEVEL = 'info'
    DEFAULT_LOG_FILES = 'stderr' + CONFIG_FILE_SEPARATOR + 'temp'
    DEFAULT_LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s'

    SPECIAL_FILES = {
        'stderr': lambda: open("/dev/stderr", "w"),
        'temp': _get_tmp_file,
    }

    def __init__(self):
        self.core = None
        self.log_file_paths = set()
        self.log_handler = _LogHandler()
        logging.getLogger().addHandler(self.log_handler)

    def get_interfaces(self):
        return []

    def get_deps(self):
        return [
            {
                'interface': 'configuration',
                'defaults': ['openpaperwork_core.config_file'],
            },
        ]

    def init(self, core):
        self.core = core

        core.call_all(
            'config_add_observer', self.CONFIG_SECTION, self._reload_config
        )
        self._reload_config()

    def _disable_logging(self):
        for fd in self.log_handler.out_fds:
            fd.close()
        self.log_handler.out_fds = set()

    def _enable_logging(self):
        if self.log_file_paths is None:
            return
        for file_path in self.log_file_paths:
            if sys.stderr is not None:  # if app is frozen
                sys.stderr.write("Writing logs to {}\n".format(file_path))
            if file_path.lower() not in self.SPECIAL_FILES:
                self.log_handler.out_fds.add(open(file_path, 'a'))
            else:
                self.log_handler.out_fds.add(
                    self.SPECIAL_FILES[file_path.lower()]()
                )

    def _reload_config(self):
        self._disable_logging()
        try:
            log_level = self.core.call_success(
                'config_get', self.CONFIG_SECTION, self.CONFIG_LOG_LEVEL,
                self.DEFAULT_LOG_LEVEL
            )
            logging.getLogger().setLevel(self.LOG_LEVELS[log_level])
            self.log_file_paths = self.core.call_success(
                'config_get', self.CONFIG_SECTION, self.CONFIG_LOG_FILES,
                self.DEFAULT_LOG_FILES
            ).split(self.CONFIG_FILE_SEPARATOR)
            self.log_handler.formatter = logging.Formatter(
                self.core.call_success(
                    'config_get', self.CONFIG_SECTION, self.CONFIG_LOG_FORMAT,
                    self.DEFAULT_LOG_FORMAT
                ) + "\n"
            )
        finally:
            self._enable_logging()
