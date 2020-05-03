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
import logging

import openpaperwork_core
import openpaperwork_core.promise

import paperwork_backend.docimport

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = False

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                "interface": "fs",
                "defaults": "openpaperwork_gtk.fs.gio",
            },
            {
                "interface": "import",
                "defaults": [
                    'paperwork_backend.docimport.img',
                    'paperwork_backend.docimport.pdf',
                ],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'import', help=_(
                "Import file(s)"
            )
        )
        p.add_argument(
            '--doc_id', '--doc', '-d', type=str, required=False,
            help=_("Target document for import")
        )
        p.add_argument(
            'files', type=str, nargs='*',
            help=_("Files to import")
        )

    def _file_import_to_dict(self, file_import):
        return {
            "imported": list(file_import.imported_files),
            "ignored": list(file_import.ignored_files),
            "new_docs": list(file_import.new_doc_ids),
            "upd_docs": list(file_import.upd_doc_ids),
            "stats": dict(file_import.stats)
        }

    def cmd_run(self, args):
        if args.command != 'import':
            return None

        file_import = paperwork_backend.docimport.FileImport(
            [self.core.call_success("fs_safe", f) for f in args.files],
            active_doc_id=args.doc_id
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        choice = 0

        if len(importers) <= 0:
            if self.interactive:
                print(
                    _("Don't know how to import file(s) %s") % args.files
                )
            LOGGER.warning("Don't know how to import file(s) %s", args.files)
            return self._file_import_to_dict(file_import)

        if len(importers) > 1:
            if not self.interactive:
                LOGGER.warning(
                    "Found many ways to import file(s) %s. Running in"
                    " non-interactive mode. Cannot request which method"
                    " must be used", args.files
                )
                return self._file_import_to_dict(file_import)
            print(_("Found many ways to import file(s) %s:") % args.files)
            choice = -1
            while choice not in range(0, len(importers)):
                for (idx, importer) in enumerate(importers):
                    print("  {} - {}".format(idx + 1, importer.get_name()))
                choice = int(input()) - 1

        importer = importers[choice]
        del importers

        promise = importer.get_import_promise()

        if self.interactive:
            print(_("Importing %s ...") % args.files)
        self.core.call_success(
            "mainloop_schedule", self.core.call_success,
            "transaction_schedule", promise
        )
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_success("mainloop")
        if self.interactive:
            print(_("Done"))
            print(_("Import result:"))
            print(_("- Imported files: %s") % file_import.imported_files)
            print(_("- Non-imported files: %s") % file_import.ignored_files)
            print(_("- New documents: %s") % file_import.new_doc_ids)
            print(_("- Updated documents: %s") % file_import.upd_doc_ids)
            for (k, v) in file_import.stats.items():
                print("- {}: {}".format(k, v))

        return self._file_import_to_dict(file_import)
