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

from .. import (_, PluginBase)


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = True

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        application = self.core.call_success("config_get_plugin_list_name")

        config_parser = parser.add_parser(
            'plugins', help=(_("Manage %s plugins") % application)
        )

        subparser = config_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )

        subparser.add_parser(
            'list', help=(
                _("Show plugins enabled for %s") % application
            )
        )

        p = subparser.add_parser(
            'add', help=(
                _("Add plugin in %s") % application
            )
        )
        p.add_argument('plugin_name')

        p = subparser.add_parser(
            'remove', help=(
                _("Remove plugin from %s") % application
            )
        )
        p.add_argument('plugin_name')

        subparser.add_parser(
            'reset', help=(_("Reset plugin list to default"))
        )

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_run(self, args):
        if args.command != 'plugins':
            return None
        elif args.subcommand == "list":
            return self._cmd_list_plugins()
        elif args.subcommand == "add":
            return self._cmd_add_plugin(args.plugin_name)
        elif args.subcommand == "remove":
            return self._cmd_remove_plugin(args.plugin_name)
        elif args.subcommand == "reset":
            return self._cmd_reset_plugins()
        else:
            return None

    def _cmd_add_plugin(self, plugin_name):
        self.core.call_all(
            "config_add_plugin", plugin_name
        )
        self.core.call_all("config_save")
        if self.interactive:
            self.core.call_all(
                "print", _("Plugin {} added").format(plugin_name) + "\n"
            )
            self.core.call_all("print_flush")
        return True

    def _cmd_remove_plugin(self, plugin_name):
        self.core.call_all(
            "config_remove_plugin", plugin_name
        )
        self.core.call_all("config_save")
        if self.interactive:
            self.core.call_all(
                "print", _("Plugin {} removed").format(plugin_name) + "\n"
            )
            self.core.call_all("print_flush")
        return True

    def _cmd_list_plugins(self):
        plugins = self.core.call_success("config_list_plugins")
        if self.interactive:
            self.core.call_all("print", "  " + _("Active plugins:") + "\n")
            for plugin in plugins:
                self.core.call_all("print", plugin + "\n")
            self.core.call_all("print_flush")
        return list(plugins)

    def _cmd_reset_plugins(self):
        self.core.call_success("config_reset_plugins")
        self.core.call_all("config_save")
        if self.interactive:
            print("Plugin list reseted")
        return True
