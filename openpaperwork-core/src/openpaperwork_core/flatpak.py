import logging
import os
import shutil
import tempfile

from . import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 75

    def __init__(self):
        super().__init__()
        self.tmp_files = set()

        self.flatpak = False
        self.tmp_dir = None

    def get_interfaces(self):
        return [
            'flatpak',
            'stats',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.flatpak = (os.name == 'posix') and self.core.call_success(
            "fs_isdir", "file:///app"
        ) is not None
        LOGGER.info("Flatpak environment: %s", self.flatpak)
        if self.flatpak:
            self.tmp_dir = self.core.call_success(
                "fs_join",
                self.core.call_success("paths_get_data_dir"), "tmp"
            )
            self.core.call_all("fs_mkdir_p", self.tmp_dir)

    def is_in_flatpak(self):
        if self.flatpak:
            return True
        return None

    def fs_mktemp(self, prefix=None, suffix=None, mode='w+b', **kwargs):
        """
        Modifies slightly the behaviour of fs_mktemp():

        When making a bug report, we use temporary files. We need the user
        to be able to access those temporary files with external applications.

        With Flatpak, the easiest way for that is to place the temporary files
        somewhere in the user home directory.
        """
        if not self.flatpak:
            return None

        tmp = tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, delete=False, mode=mode,
            dir=self.core.call_success("fs_unsafe", self.tmp_dir)
        )
        LOGGER.info("Flatpak tmp file: %s --> %s", self.tmp_dir, tmp.name)
        self.tmp_files.add(tmp.name)
        return (self.core.call_success("fs_safe", tmp.name), tmp)

    def on_quit(self):
        if not self.flatpak:
            return
        shutil.rmtree(self.core.call_success("fs_unsafe", self.tmp_dir))

    def stats_get(self, out: dict):
        if not self.flatpak:
            return

        if 'os_name' in out:
            out['os_name'] += ' (flatpak)'
        else:
            out['os_name'] = 'GNU/Linux (flatpak)'
