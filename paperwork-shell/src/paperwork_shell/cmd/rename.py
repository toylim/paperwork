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
        super().__init__()
        self.interactive = False

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                "interface": "document_storage",
                "defaults": ['paperwork_backend.model.workdir'],
            },
        ]

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'rename', help=_("Change a document identifier")
        )
        p.add_argument(
            'source_doc_id',
            help=_("Document to rename")
        )
        p.add_argument(
            'dest_doc_id',
            help=_("New name for the document")
        )

    def cmd_run(self, args):
        if args.command != 'rename':
            return None

        source_doc_id = args.source_doc_id
        dest_doc_id = args.dest_doc_id

        source_doc_url = self.core.call_success("doc_id_to_url", source_doc_id)
        dest_doc_url = self.core.call_success("doc_id_to_url", dest_doc_id)

        if self.interactive:
            print("Renaming: {} --> {}".format(source_doc_url, dest_doc_url))

        self.core.call_all("doc_rename_by_url", source_doc_url, dest_doc_url)

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 2)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.del_obj(source_doc_id)
        for transaction in transactions:
            transaction.add_obj(dest_doc_id)
        for transaction in transactions:
            transaction.commit()

        if self.interactive:
            print("{} renamed into {}".format(source_doc_id, dest_doc_id))

        return True