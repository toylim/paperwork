"""
Used to archive logs, screenshots, etc.
Do not depends on 'fs' plugins (this plugin is used for logging and therefore
is critical --> has minimum dependencies).
"""

import datetime
import logging
import os
import os.path

from . import PluginBase


LOGGER = logging.getLogger(__name__)
ARCHIVE_FILE_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31


class ArchiveHandler(object):
    def __init__(self, storage_name, storage_dir, file_extension):
        self.storage_name = storage_name
        self.storage_dir = storage_dir
        self.file_extension = file_extension

    def get_new(self, name=None):
        if name is None:
            name = self.storage_name
        out_file_name = datetime.datetime.now().strftime(
            ARCHIVE_FILE_DATE_FORMAT
        )
        out_file_name += "_{}.{}".format(name, self.file_extension)
        out_file_path = os.path.join(self.storage_dir, out_file_name)
        return out_file_path

    def get_archived(self):
        for f in os.listdir(self.storage_dir):
            if not f.lower().endswith(".{}".format(self.file_extension)):
                continue
            short_f = "_".join(f.split("_", 3)[:3])
            try:
                date = datetime.datetime.strptime(
                    short_f, ARCHIVE_FILE_DATE_FORMAT
                )
            except ValueError as exc:
                LOGGER.warning(
                    "Unexpected filename: %s. Ignoring it",
                    f, exc_info=exc
                )
                continue
            yield (date, os.path.join(self.storage_dir, f))

    def delete_obsoletes(self):
        now = datetime.datetime.now()
        for (date, file_path) in self.get_archived():
            if (now - date).days <= MAX_DAYS:
                continue
            LOGGER.info("Deleting obsolete log file: %s", file_path)
            os.unlink(file_path)


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['file_archives']

    def init(self, core):
        super().init(core)
        local_dir = os.path.expanduser("~/.local")
        data_dir = os.getenv(
            "XDG_DATA_HOME", os.path.join(local_dir, "share")
        )
        self.base_archive_dir = os.path.join(
            data_dir, "openpaperwork"
        )
        os.makedirs(self.base_archive_dir, exist_ok=True)

        LOGGER.info("Archiving to %s", self.base_archive_dir)

    def file_archive_get(self, storage_name, file_extension):
        storage_dir = os.path.join(
            self.base_archive_dir, storage_name
        )
        LOGGER.info("Archiving '%s' to %s", storage_name, storage_dir)
        os.makedirs(storage_dir, exist_ok=True)
        archiver = ArchiveHandler(storage_name, storage_dir, file_extension)
        archiver.delete_obsoletes()
        return archiver
