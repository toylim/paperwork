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

import openpaperwork_core

_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = True
        self.changes = None

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return {
            'interfaces': [
                ('syncable', [
                    "paperwork_backend.guesswork.label.simplebayes",
                    "paperwork_backend.guesswork.ocr.pyocr",
                    "paperwork_backend.index.whoosh",
                    "paperwork_backend.model.labels",
                ]),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        parser.add_parser('sync', help=_(
            "Synchronize the index(es) with the content of the work directory"
        ))

    def on_sync(self, name, status, key):
        self.changes[name][status].append(key)

    def cmd_run(self, args):
        if args.command != 'sync':
            return None

        if self.interactive:
            print(_("Synchronizing with work directory ..."))

        self.changes = collections.defaultdict(
            # we cannot use sets here because sets are not JSON-serializable
            lambda: collections.defaultdict(list)
        )
        promises = []
        self.core.call_all("sync", promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)

        self.core.call_one("schedule", promise.schedule)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        if self.interactive:
            print(_("All done !"))

        # ensure order of documents to make testing easier and ensure
        # behaviour consistency
        for actions in self.changes.values():
            for docs in actions.values():
                docs.sort()
        return dict(self.changes)
