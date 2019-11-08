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
import openpaperwork_core.promise

from . import util


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
                "interface": "fs",
                "defaults": ["paperwork_backend.fs.gio"],
            },
            {
                "interface": "export_pipes",
                "defaults": [
                    'paperwork_backend.docexport.img',
                    'paperwork_backend.docexport.pdf',
                    'paperwork_backend.docexport.pillowfight',
                ],
            },
        ]

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'export', help=_(
                "Export a document, a page, or a set of pages."
                " Example:"
                " paperwork-cli export 20150303_2314_39 -p 2 -f img_boxes"
                " -f grayscale -f jpeg -o ~/tmp/pouet.jpg"
            )
        )
        p.add_argument('doc_id', help=_('Document to export'))
        p.add_argument(
            '--pages', '-p', type=str, required=False,
            help=_(
                "Pages to export"
                " (single integer, range or comma-separated list,"
                " default: all pages)"
            )
        )
        p.add_argument(
            '--filters', '-f', nargs=1, action='append',
            type=str, required=False,
            help=_(
                "Export filters. Specify this option once for each filter"
                " to apply (ex: '-f grayscale -f jpeg'."
            )
        )
        p.add_argument(
            '--out', '-o', type=str, required=False,
            help=_(
                "Output file/directory. If not specify, will list"
                " the filters that could be chained after those already"
                " specified."
            )
        )

    def cmd_run(self, args):
        if args.command != 'export':
            return None

        # argument parsing

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        pages = util.parse_page_list(args)
        filters = args.filters if args.filters is not None else []
        out = args.out

        if pages is None or len(pages) <= 0:
            input_value = doc_url
        elif len(pages) == 1:
            input_value = (doc_url, pages)
        else:
            input_value = (doc_url, pages)

        if len(filters) <= 0:
            output_type = None
        else:
            filters = [x[0] for x in filters]
            filters = [
                self.core.call_success('export_get_pipe_by_name', f)
                for f in filters
            ]
            if None in filters:
                print(_("Unknown filters: %s") % filters)
                sys.exit(1)
            output_type = filters[-1].output_type

        # If no output is provided
        if out is None or out == "":
            next_pipes = []
            if output_type is not None:
                self.core.call_all(
                    "export_get_pipes_by_input", next_pipes, output_type
                )
            elif pages is not None and len(pages) > 0:
                self.core.call_all(
                    "export_get_pipes_by_page", next_pipes, doc_url, pages[0]
                )
            else:
                self.core.call_all(
                    "export_get_pipes_by_doc_url", next_pipes, doc_url
                )
            next_pipes = [pipe.name for pipe in next_pipes]
            if self.interactive:
                print(
                    _("Current filters: %s") % [pipe.name for pipe in filters]
                )
                if len(next_pipes) > 0:
                    print(_("Next possible filters:"))
                    for pipe in next_pipes:
                        print("- " + pipe)
                elif len(filters) > 0:
                    print(_(
                        "'%s' is an output filter. Not other filter can be"
                        " added after '%s'."
                    ) % (filters[-1].name, filters[-1].name))
                else:
                    print(_("No possible filters found"))
            return next_pipes

        # else try to export
        out = self.core.call_success("fs_safe", out)

        def get_input_value():
            return input_value

        promise = openpaperwork_core.promise.Promise(
            self.core, get_input_value
        )
        for pipe in filters:
            promise = promise.then(
                pipe.get_promise(result='final', target_file_url=out)
            )

        sys.stdout.write(_("Exporting to %s ... ") % out)
        sys.stdout.flush()
        self.core.call_one("schedule", promise.schedule)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        sys.stdout.write(_("Done"))
        return self.core.call_success("fs_exists", out) is not None
