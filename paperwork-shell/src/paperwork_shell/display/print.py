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
import os
import sys
import subprocess

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    MIN_LINES_FOR_PAGING = 25

    def __init__(self):
        self.output = []

    def get_interfaces(self):
        return ['print']

    def print(self, txt):
        self.output.append(txt)

    def print_isatty(self):
        return os.isatty(sys.stdout.fileno())

    def print_flush(self):
        output = "".join(self.output)
        self.output = []
        nb_lines = output.count("\n")
        isatty = os.isatty(sys.stdout.fileno())

        if nb_lines < self.MIN_LINES_FOR_PAGING or not isatty:
            sys.stdout.write(output)
        else:
            # we always use 'less -R' because it's the only one we are sure
            # that handles correctly our ANSI colors
            process = subprocess.Popen(('less', '-R'), stdin=subprocess.PIPE)
            # TODO(Jflesch): Charset. For now we assume the system is UTF-8
            try:
                process.stdin.write(output.encode("utf-8"))
                process.communicate()
            except BrokenPipeError:
                pass
