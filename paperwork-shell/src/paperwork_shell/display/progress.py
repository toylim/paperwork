#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2019  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
import collections
import gettext
import logging
import shutil
import sys
import threading
import time

import openpaperwork_core

_ = gettext.gettext

LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_PROGRESS = 0.3


def print_progress(upd_type, progress, description=None):
    eol = "\r"
    if description is None:
        description = ""
    if progress >= 1.0:
        if description is None:
            description = _("Done")
        eol = "\n"

    str_progress = (
        "=" * int(progress * 20)
        + " " * (20 - int(progress * 20))
    )
    line = '%3d%% [%s] ' % (progress * 100, str_progress[:20])
    line += '[%-20s] %s' % (upd_type[:20], description)

    term_width = shutil.get_terminal_size((500, 25)).columns
    line = line[:term_width - 1]
    sys.stdout.write("\033[K" + line + eol)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.progresses = collections.OrderedDict()
        self.thread = None
        self.lock = threading.Lock()
        self.interactive = False
        self.enabled = True

    def get_interfaces(self):
        return [
            'progress_listener',
        ]

    def _thread(self):
        while True:
            time.sleep(TIME_BETWEEN_PROGRESS)

            with self.lock:
                if len(self.progresses) <= 0:
                    self.thread = None
                    return
                if not self.enabled:
                    continue

                upd_type = next(iter(self.progresses))
                (progress, description) = self.progresses[upd_type]
                print_progress(upd_type, progress, description)

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def shell_show_progress(self, enabled):
        self.enabled = enabled

    def on_progress(self, upd_type, progress, description=None):
        if not self.interactive:
            return

        with self.lock:
            if progress > 1.0:
                LOGGER.warning(
                    "Invalid progression (%f) for [%s]",
                    progress, upd_type
                )
                progress = 1.0
            if progress >= 1.0:
                if upd_type not in self.progresses:
                    return
                self.progresses.pop(upd_type)
                print_progress(upd_type, progress)
            else:
                self.progresses[upd_type] = (progress, description)

            if self.thread is None:
                self.thread = threading.Thread(target=self._thread)
                self.thread.daemon = True
                self.thread.start()
