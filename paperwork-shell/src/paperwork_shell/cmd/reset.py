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
import logging
import shutil
import sys

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)
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
                # optional dependency
                # ('img_renderer', [
                #     'paperwork_shell.display.docrendering.img'
                # ]),
                ('page_reset', ['paperwork_backend.model.img_overlay',]),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ])
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        reset_parser = parser.add_parser(
            'reset', help=_("Reset a page to its original content")
        )
        # for safety, we mark the argument --pages as required
        reset_parser.add_argument('--pages', '-p', type=str, required=True)
        reset_parser.add_argument('doc_id')

    def show_page(self, doc_url, page_idx):
        if not self.interactive:
            return

        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        img = self.core.call_success("url_to_pillow", page_url)

        terminal_width = shutil.get_terminal_size()[0] - 1
        img = self.core.call_success(
            "img_render", img, terminal_width=terminal_width
        )
        if img is None:
            return
        for line in img:
            print(line)
        print()

    def cmd_run(self, args):
        if args.command != 'reset':
            return None

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        pages = util.parse_page_list(args)
        out = []

        for page_idx in pages:
            out.append((doc_id, page_idx))
            if self.interactive:
                print(
                    _("Reseting document {} page {} ...").format(
                        doc_id, page_idx
                    )
                )
                print(_("Original:"))
                self.show_page(doc_url, page_idx)

            self.core.call_all("page_reset_by_url", doc_url, page_idx)

            if self.interactive:
                print(_("Reseted:"))
                self.show_page(doc_url, page_idx)
                print("")

        if self.interactive:
            sys.stdout.write(_("Committing ...") + " ")
            sys.stdout.flush()

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.upd_obj(doc_id)
        for transaction in transactions:
            transaction.commit()

        if self.interactive:
            print(_("Done"))
            print(_("All done !"))

        return out
