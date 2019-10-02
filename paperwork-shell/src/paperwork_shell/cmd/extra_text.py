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
                ('extra_text', ['paperwork_backend.model.extra_text',]),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        extra_text_parser = parser.add_parser(
            'extra_text', help=_(
                "Manage additional text attached to documents"
            )
        )

        subparser = extra_text_parser.add_subparsers(
            help=_('sub-command'), dest='subcommand', required=True
        )

        parser = subparser.add_parser(
            'get', help=_("Get a document additional text")
        )
        parser.add_argument('doc_id')

        parser = subparser.add_parser(
            'set', help=_("Set a document additional text")
        )
        parser.add_argument('doc_id')
        parser.add_argument('text')

    def cmd_run(self, args):
        if args.command != 'extra_text':
            return None
        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        if args.subcommand == "get":
            return self._cmd_get(doc_id, doc_url)
        elif args.subcommand == "set":
            return self._cmd_set(doc_id, doc_url, args.text)
        else:
            return None

    def _cmd_get(self, doc_id, doc_url):
        text = []
        self.core.call_success("doc_get_extra_text_by_url", text, doc_url)
        if self.interactive:
            if len(text) > 0:
                print("  " + _("Additional text:"))
                print("\n".join(text))
            else:
                print(_("No additional text"))
        return text

    def _cmd_set(self, doc_id, doc_url, text):
        text = text.strip()
        self.core.call_success("doc_set_extra_text_by_url", doc_url, text)
        if self.interactive:
            print(_("Done"))
        return True
