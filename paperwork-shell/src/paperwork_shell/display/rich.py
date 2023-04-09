#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2023  Jerome Flesch
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
import rich.text

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000
    NB_LINES_FOR_PAGER = 50

    def __init__(self):
        self.output = []
        self.console = None

    def get_interfaces(self):
        return ['print']

    def cmd_set_console(self, console):
        self.console = console

    def print(self, txt):
        self.output.append(txt)
        return True

    def print_isatty(self):
        if self.console is not None:
            return True
        return None

    def print_flush(self):
        if self.console is None:
            return None
        output = rich.text.Text("\n").join([
            rich.text.Text.from_ansi(line)
            for line in self.output
        ])
        if len(self.output) >= self.NB_LINES_FOR_PAGER:
            # 'less -r' is pretty much one of the only pager for which
            # we are sure that ANSI escape codes will work
            os.environ['PAGER'] = 'less -r'
            with self.console.console.pager(styles=True):
                self.console.console.print(output)
        else:
            self.console.console.print(output)
        self.output = []
        return True
