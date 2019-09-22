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

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext

# Only basic types are handled by shell commands
CMD_VALUE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
}


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return {
            'interfaces': [
                ('paperwork_config', ['paperwork_backend.config.file',]),
            ],
        }

    def cmd_complete_argparse(self, parser):
        application = self.core.call_success("paperwork_get_application_name")

        config_parser = parser.add_parser('config')
        subparser = config_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )
        get_parser = subparser.add_parser(
            'get', help=_("Get a value from Paperwork's configuration")
        )
        get_parser.add_argument('opt_name')

        put_parser = subparser.add_parser(
            'put', help=_("Set a value in Paperwork's configuration")
        )
        put_parser.add_argument('opt_name')
        put_parser.add_argument('type')
        put_parser.add_argument('value')

        subparser.add_parser(
            'show', help=_("Show Paperwork's configuration")
        )

        subparser.add_parser(
            'list_types', help=_(
                "Show value types you can use from command line"
            )
        )

        subparser.add_parser(
            'list_plugins', help=(
                _("Show plugins enabled for %s") % application
            )
        )

        add_plugin_parser = subparser.add_parser(
            'add_plugin', help=(
                _("Add plugin in %s") % application
            )
        )
        add_plugin_parser.add_argument('plugin_name')

        remove_plugin_parser = subparser.add_parser(
            'remove_plugin', help=(
                _("Remove plugin from %s") % application
            )
        )
        remove_plugin_parser.add_argument('plugin_name')

    def cmd_run(self, args, **kwargs):
        if args.command != 'config':
            return None
        if args.subcommand == "get":
            return self._cmd_get(args.opt_name, **kwargs)
        elif args.subcommand == "put":
            return self._cmd_put(args.opt_name, args.type, args.value, **kwargs)
        elif args.subcommand == "show":
            return self._cmd_show(**kwargs)
        elif args.subcommand == "list_types":
            return self._cmd_list_types(**kwargs)
        elif args.subcommand == "list_plugins":
            return self._cmd_list_plugins(**kwargs)
        elif args.subcommand == "add_plugin":
            return self._cmd_add_plugin(args.plugin_name, **kwargs)
        elif args.subcommand == "remove_plugin":
            return self._cmd_remove_plugin(args.plugin_name, **kwargs)
        else:
            return None

    def _cmd_get(self, opt_name, interactive=False):
        v = self.core.call_success("paperwork_config_get", opt_name)
        if v is None:
            LOGGER.warning("No such option '%s'", opt_name)
            return None
        if interactive:
            print("{} = {}".format(opt_name, v))
        return {opt_name: v}

    def _cmd_put(self, opt_name, vtype, value, interactive=False):
        value = CMD_VALUE_TYPES[vtype](value)
        if interactive:
            print("{} = {}".format(opt_name, value))
        self.core.call_all("paperwork_config_put", opt_name, value)
        self.core.call_all("paperwork_config_save")
        return {opt_name: value}

    def _cmd_show(self, interactive=False):
        opts = self.core.call_success("paperwork_config_list_options")
        out = {}
        for opt in opts:
            out[opt] = self.core.call_success("paperwork_config_get", opt)
            if interactive:
                print("{} = {}".format(opt, out[opt]))
        return out

    def _cmd_list_types(self, interactive=False):
        r = list(CMD_VALUE_TYPES.keys())
        if interactive:
            print(r)
        return r

    def _cmd_add_plugin(self, plugin_name, interactive=False):
        self.core.call_all("paperwork_config_add_plugin", plugin_name)
        self.core.call_all("paperwork_config_save")
        if interactive:
            print(_("Plugin {} added").format(plugin_name))
        return True

    def _cmd_remove_plugin(self, plugin_name, interactive=False):
        self.core.call_all("paperwork_config_remove_plugin", plugin_name)
        self.core.call_all("paperwork_config_save")
        if interactive:
            print(_("Plugin {} removed").format(plugin_name))
        return True

    def _cmd_list_plugins(self, interactive=False):
        plugins = self.core.call_success("paperwork_config_list_plugins")
        if interactive:
            print("  " + _("Active plugins:"))
            for plugin in plugins:
                print(plugin)
        return list(plugins)
