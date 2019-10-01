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
                ('doc_renderer', [
                    # if there are none loaded, nothing it displayed, which
                    # may be fine.
                    # (see paperwork-json)
                ]),
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('index', ['paperwork_backend.index.shell',])
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'search', help=_("Search keywords in documents")
        )
        p.add_argument(
            '--limit', '-l', type=int, default=50,
            help=_("Maximum number of results (default: 50)")
        )
        p.add_argument(
            'keywords', nargs='*', default=[],
            help=_("Search keywords (none means all documents)")
        )

    def cmd_run(self, args):
        if args.command != 'search':
            return None

        keywords = " ".join(args.keywords)

        doc_ids = []
        self.core.call_all("index_search", doc_ids, keywords, args.limit)

        renderers = []
        self.core.call_all("doc_renderer_get", renderers)
        assert(len(renderers) > 0)
        renderer = renderers[-1]

        if self.interactive:
            for doc_id in doc_ids:
                header = _("Document id: %s") % doc_id
                self.core.call_all("print", header + "\n")
                doc_url = self.core.call_success("doc_id_to_url", doc_id)
                lines = renderer.get_preview_output(
                    doc_id, doc_url,
                    shutil.get_terminal_size((80, 25))
                )
                for line in lines:
                    self.core.call_all("print", line + "\n")
                self.core.call_all("print", "\n")
            self.core.call_all("print_flush")

        return doc_ids
