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
                ('document_storage', ['paperwork_backend.model.workdir']),
                ('pages', [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.thumbnail',
                ])
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'delete', help=_("Delete a document or a page")
        )
        p.add_argument(
            '--pages', '-p', type=str, required=False,
            help=_(
                "Pages to delete"
                " (single integer, range or comma-separated list,"
                " default: all pages)"
            )
        )
        p.add_argument(
            'doc_ids', nargs='*', default=[],
            help=_("Target documents")
        )

    def cmd_run(self, args):
        if args.command != 'delete':
            return None

        doc_ids = args.doc_ids

        for doc_id in doc_ids:
            if "/" in doc_id or "\\" in doc_id or ".." in doc_id:
                print("Invalid doc_id: {}".format(doc_id))
                sys.exit(2)

        pages = util.parse_page_list(args)

        del_doc_msg = _("Deleting document %s ...")
        del_page_msg = _("Deleting page %d of document %s ...")

        for doc_id in doc_ids:
            if self.interactive:
                if pages is None:
                    r = util.ask_confirmation(
                        _("Delete document %s ?") % str(doc_id),
                        default='n'
                    )
                else:
                    r = util.ask_confirmation(
                        _("Delete page(s) %s of document %s ?") % (
                            str([p + 1 for p in pages]), str(doc_id)
                        ), default='n'
                    )
                if r != 'y':
                    continue

            if pages is None:
                if self.interactive:
                    print(del_doc_msg % doc_id)
                self.core.call_all("storage_delete_doc_id", doc_id)
            else:
                for page in pages:
                    doc_url = self.core.call_success(
                        "doc_id_to_url", doc_id
                    )
                    if self.interactive:
                        print(del_page_msg % (page + 1, doc_id))
                    self.core.call_all("page_delete", doc_url, page)

        transactions = []
        self.core.call_all(
            "doc_transaction_start", transactions, len(doc_ids)
        )

        for transaction in transactions:
            for doc_id in doc_ids:
                doc_url = self.core.call_success("doc_id_to_url", doc_id)
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                if nb_pages is None or nb_pages <= 0:
                    transaction.del_obj(doc_id)
                else:
                    transaction.upd_obj(doc_id)

        for transaction in transactions:
            transaction.commit()

        return True
