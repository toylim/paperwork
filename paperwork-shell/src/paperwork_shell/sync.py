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

import openpaperwork_core

_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.interactive = True

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return {
            'interfaces': [
                ('syncable', [
                    "paperwork_backend.guesswork.label_guesser",
                    "paperwork_backend.index.whoosh",
                    "paperwork_backend.model.labels",
                    "paperwork_backend.ocr.pyocr",
                ]),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        parser.add_parser('sync')

    def cmd_run(self, args):
        if args.command != 'sync':
            return None

        print(_("Synchronizing with work directory ..."))

        promises = []
        self.core.call_all("sync", promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)

        self.core.call_one("schedule", p.schedule)
        self.core.call_one(
            "schedule", self.core.call_all, "mainloop_quit_graceful"
        )
        self.core.call_one("mainloop")
        if self.interactive:
            print(_("All done !"))
        return True
