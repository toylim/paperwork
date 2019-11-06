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


_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = False
        self.out = []

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return {
            'interfaces': [
                ('mainloop', ['openpaperwork_core.mainloop_asyncio']),
                ('scan', ['paperwork_backend.docscan.libinsane']),
            ],
        }

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        scanner_parser = parser.add_parser(
            'scanner', help=_("Manage scanner configuration")
        )
        subparser = scanner_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )
        subparser.add_parser(
            'list', help=_("List all scanners and their possible settings")
        )

    def _get_scanner_info(self, dev, dev_id, dev_name):
        if self.interactive:
            print(_("Examining scanner {} ...").format(dev_id))
        dev_out = {
            'id': dev_id,
            'name': dev_name,
            'sources': [],
        }
        sources = dev.get_sources()
        for (source_id, source) in sources.items():
            source_out = {
                "id": source_id,
                "resolutions": source.get_resolutions(),
            }
            dev_out['sources'].append(source_out)
        self.out.append(dev_out)
        return dev

    def _get_scanners_info(self, devs):
        promise = openpaperwork_core.promise.Promise(self.core)
        for (dev_id, dev_name) in devs:
            promise = promise.then(self.core.call_success(
                "scan_get_scanner_promise", dev_id
            ))
            promise = promise.then(self._get_scanner_info, dev_id, dev_name)
            promise = promise.then(lambda scanner: scanner.close())
        promise.schedule()

    def _list_scanners(self):
        self.out = []

        promise = self.core.call_success("scan_list_scanners_promise")
        promise = promise.then(self._get_scanners_info)
        promise.schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

    def _print_scanners(self):
        if self.interactive:
            print("")
            for dev in self.out:
                print(dev['name'])
                print(" |-- " + _("ID:") + " " + dev['id'])
                for source in dev['sources']:
                    print(" |-- " + _("Source:") + " " +  source['id'])
                    print(
                        " |    |-- " + _("Resolutions:")
                        + " " + str(source['resolutions'])
                    )
                print("")


    def cmd_run(self, args):
        if args.command != 'scanner':
            return None

        if args.subcommand == 'list':
            self._list_scanners()
            self._print_scanners()
            return self.out
        elif args.subcommand == 'set':
            return self._set_scanner(args)
        elif args.subcommand == 'get':
            return self._get_scanner()
        assert()
