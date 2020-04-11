import datetime
import gettext
import logging
import os
import os.path

from .. import PluginBase


LOGGER = logging.getLogger(__name__)
LOG_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31
_ = gettext.gettext


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
        self.out_file_path = os.path.join(self.logs_dir, out_file_name)
        self.formatter = logging.Formatter(self.LOG_FORMAT)
        self.out_fd = open(self.out_file_path, 'w')

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
                fd.write(line.line)
                line = line.next


class Plugin(PluginBase):
    PRIORITY = -10000

    def __init__(self):
        super().__init__()
        logging.getLogger().setLevel(logging.INFO)

    def get_interfaces(self):
        return [
            'bug_report_attachments',
            'log_archiver',
        ]

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
        self.logs_dir = os.path.join(
            data_dir, "openpaperwork", "logs"
        )
        os.makedirs(self.logs_dir, exist_ok=True)

        self.log_handler = LogHandler(self.logs_dir)
        logging.getLogger().addHandler(self.log_handler)

        LOGGER.info("Archiving logs to %s", self.log_handler.out_file_path)

        self._delete_obsolete_logs()

    def _get_log_files(self):
        for f in os.listdir(self.logs_dir):
            if not f.lower().endswith(".txt"):
                continue
            short_f = "_".join(f.split("_", 3)[:3])
            try:
                date = datetime.datetime.strptime(short_f, LOG_DATE_FORMAT)
            except ValueError as exc:
                LOGGER.warning("Unexpected filename: %s", f, exc_info=exc)
                continue
            yield (date, os.path.join(self.logs_dir, f))

    def _delete_obsolete_logs(self):
        now = datetime.datetime.now()
        for (date, file_path) in self._get_log_files():
            if (now - date).days <= MAX_DAYS:
                continue
            LOGGER.info("Deleting obsolete log file: %s", file_path)
            os.unlink(file_path)

    def on_uncaught_exception(self, exc_info):
        self.log_handler.log_uncaught_exception()

    def bug_report_get_attachments(self, inputs: dict):
        for (date, file_path) in self._get_log_files():
            file_url = "file://" + file_path
            inputs[file_url] = {
                'date': date,
                'include_by_default': False,
                'file_type': _("Log file"),
                'file_url': file_url,
                'file_size': os.stat(file_path).st_size
            }

        file_url = "file://" + self.log_handler.out_file_path
        inputs[file_url] = {
            'date': None,  # now
            'include_by_default': True,
            'file_type': _("Log file"),
            'file_url': file_url,
            'file_size': os.stat(file_path).st_size
        }
