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

from . import util


_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = False

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_labels', ['paperwork_backend.model.labels',]),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        label_parser = parser.add_parser('label')
        subcmd_parser = label_parser.add_subparsers(
            help=_("label command"), dest='sub_command', required=True
        )

        subcmd_parser.add_parser('list')
        subcmd_parser.add_parser('show')

    def cmd_run(self, args):
        if args.command != 'label':
            return None

        if args.sub_command == 'list':
            if self.interactive:
                sys.stdout.write(_("Loading all labels ... "))
                sys.stdout.flush()
            promises = []
            self.core.call_all("label_load_all", promises)
            promise = promises[0]
            for p in promises[1:]:
                promise = promise.then(p)
            self.core.call_one("schedule", promise.schedule)
            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")
            if self.interactive:
                sys.stdout.write(_("Done") + "\n")

            labels = set()
            self.core.call_all("labels_get_all", labels)
            labels = list(labels)
            labels.sort()

            if self.interactive:
                print()
                self.core.call_all("print_labels", labels)
            return labels
        elif args.sub_command == 'show':
            pass
        else:
            if self.interactive:
                print("Unknown label command: {}".format(args.sub_command))
            return None
