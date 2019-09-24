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
        self.interactive = False

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
                ('doc_renderer', [
                    "paperwork_shell.display.docrendering.img",
                    "paperwork_shell.display.docrendering.labels",
                    "paperwork_shell.display.docrendering.text",
                ]),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser('show')
        p.add_argument('doc_id')
        p.add_argument(
            '--pages', '-p', required=False,
            help="Pages to show: 1,4 or 1-10 (default: all)"
        )

    def cmd_run(self, args):
        if args.command != 'show':
            return None

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)

        if hasattr(args, 'pages') and args.pages is not None:
            if "-" in args.pages:
                pages = args.pages.split("-", 1)
                pages = range(
                    int(pages[0]) - 1,
                    min(int(pages[1]), nb_pages)
                )
            else:
                pages = [
                    (int(p) - 1) for p in args.pages.split(",")
                    if p >= 1 and p <= nb_pages
                ]
        else:
            pages = range(
                0, self.core.call_success("doc_get_nb_pages_by_url", doc_url)
            )

        renderers = []
        self.core.call_all("doc_renderer_get", renderers)
        assert(len(renderers) > 0)
        renderer = renderers[-1]

        if self.interactive:
            lines = renderer.get_doc_output(
                doc_id, doc_url,
                shutil.get_terminal_size((80, 25))
            )
            for line in lines:
                sys.stdout.write(line + "\n")
            sys.stdout.write("\n")

            for page_nb in pages:
                lines = renderer.get_page_output(
                    doc_id, doc_url, page_nb,
                    shutil.get_terminal_size((80, 25))
                )
                for line in lines:
                    sys.stdout.write(line + "\n")
                sys.stdout.write("\n")

        return {
            'document': renderer.get_doc_infos(doc_id, doc_url),
            'pages': {
                page_nb: renderer.get_page_infos(doc_id, doc_url, page_nb)
                for page_nb in pages
            },
        }
