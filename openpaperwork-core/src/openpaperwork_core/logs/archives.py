import datetime
import logging
import os
import os.path

from .. import PluginBase


LOGGER = logging.getLogger(__name__)
LOG_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31


class LogLine(object):
    def __init__(self, line):
        self.line = line
        self.next = None


class LogHandler(logging.Handler):
    LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s'
    MAX_LINES = 5000
    MAX_UNCAUGHT_LOGGUED = 20

    def __init__(self, logs_dir):
        super().__init__()
        self.logs_dir = logs_dir

        self.first_line = None
        self.last_line = None
        self.nb_lines = 0

        self.nb_uncaught_loggued = 0

        out_file_name = datetime.datetime.now().strftime(LOG_DATE_FORMAT)
        out_file_name += "_logs.txt"
        out_file_path = os.path.join(self.logs_dir, out_file_name)
        self.formatter = logging.Formatter(self.LOG_FORMAT)
        self.out_fd = open(out_file_path, 'w')

    def emit(self, record):
        line = self.formatter.format(record) + "\n"
        self.out_fd.write(line)

        line = LogLine(line)
        if self.last_line is not None:
            self.last_line.next = line
        self.last_line = line

        if self.first_line is None:
            self.first_line = line

        if self.nb_lines >= self.MAX_LINES:
            self.last_line = self.last_line.next
        else:
            self.nb_lines += 1

    def log_uncaught_exception(self):
        if self.nb_uncaught_loggued >= self.MAX_UNCAUGHT_LOGGUED:
            # avoid logging too much
            return

        self.nb_uncaught_loggued += 1

        out_file_name = datetime.datetime.now().strftime(LOG_DATE_FORMAT)
        out_file_name += "_uncaught_exception_logs.txt"
        out_file_path = os.path.join(self.logs_dir, out_file_name)
        self.formatter = logging.Formatter(self.LOG_FORMAT)

        with open(out_file_path, 'w') as fd:
            line = self.first_line
            while line is not None:
                fd.write(line)


class Plugin(PluginBase):
    PRIORITY = -10000

    def __init__(self):
        super().__init__()
        logging.getLogger().setLevel(logging.INFO)

    def get_interfaces(self):
        return ['log_archiver']

    def get_deps(self):
        return [
            {
                'interface': 'uncaught_exception',
                'defaults': ['openpaperwork_core.uncaught_exception'],
            },
        ]

    def init(self, core):
        super().init(core)
        local_dir = os.path.expanduser("~/.local")
        data_dir = os.getenv(
            "XDG_DATA_HOME", os.path.join(local_dir, "share")
        )
        logs_dir = os.path.join(
            data_dir, "openpaperwork", "logs"
        )
        os.makedirs(logs_dir, exist_ok=True)

        self.log_handler = LogHandler(logs_dir)
        logging.getLogger().addHandler(self.log_handler)

        self._delete_obsolete_logs(logs_dir)

    def _delete_obsolete_logs(self, logs_dir):
        now = datetime.datetime.now()

        for f in os.listdir(logs_dir):
            if not f.lower().endswith(".txt"):
                continue
            f = "_".join(f.split("_", 2)[:3])
            date = datetime.datetime.strptime(f, LOG_DATE_FORMAT)

            if (now - date).days <= MAX_DAYS:
                continue

            filepath = os.path.join(logs_dir, f)
            LOGGER.info("Deleting obsolete log file: %s", filepath)
            os.unlink(filepath)

    def on_uncaught_exception(self, exc_info):
        self.log_handler.log_uncaught_exception()
