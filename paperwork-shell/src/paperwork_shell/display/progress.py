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
import gettext
import shutil
import sys

import openpaperwork_core

_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.nb_written = 0

    def on_label_guesser_commit_start(self, *args, **kwargs):
        if self.nb_written > 0:
            sys.stdout.write("\n")
        self.nb_written = 0
        sys.stdout.write(
            _("Committing changes in label guesser database ...") + " "
        )
        sys.stdout.flush()

    def on_label_guesser_commit_end(self, *args, **kwargs):
        if self.nb_written > 0:
            sys.stdout.write("\n")
        self.nb_written = 0
        sys.stdout.write(_("Done") + "\n")

    def on_index_commit_start(self, *args, **kwargs):
        if self.nb_written > 0:
            sys.stdout.write("\n")
        self.nb_written = 0
        sys.stdout.write(_("Committing changes in the index ...") + " ")
        sys.stdout.flush()

    def on_index_commit_end(self, *args, **kwargs):
        if self.nb_written > 0:
            sys.stdout.write("\n")
        self.nb_written = 0
        sys.stdout.write(_("Done") + "\n")

    def on_progress(self, upd_type, progress, description=None):
        if description is None:
            if self.nb_written > 0:
                sys.stdout.write("\n")
            self.nb_written = 0
            return

        str_progress = (
            "=" * int(progress * 20)
            + " " * int((1.0 - progress) * 20)
        )
        line = '[%s] [%-20s] %s' % (
            str_progress[:20], upd_type[:20], description
        )

        term_width = shutil.get_terminal_size((500, 25)).columns
        line = line[:term_width - 1]
        sys.stdout.write("\033[K" + line + "\r")

        self.nb_written += 1
