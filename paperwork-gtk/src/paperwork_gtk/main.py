import argparse
import gettext
import json
import sys
import traceback

import openpaperwork_core

import paperwork_backend


_ = gettext.gettext

DEFAULT_GUI_PLUGINS = paperwork_backend.DEFAULT_GUI_PLUGINS + [
]


def main_main(in_args):
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin log_print first.

    core = openpaperwork_core.Core()
    core.load('openpaperwork_core.log_print')
    core.init()
    core.call_all("set_log_output", sys.stderr)
    core.call_all("set_log_level", 'warning')

    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()
    core.call_all(
        "config_load", "paperwork2", "paperwork-gtk", DEFAULT_GUI_PLUGINS
    )

    parser = argparse.ArgumentParser()
    cmd_parser = parser.add_subparsers(
        help=_('command'), dest='command', required=True
    )

    core.call_all("cmd_complete_argparse", cmd_parser)
    args = parser.parse_args(in_args)

    core.call_all("cmd_set_interactive", interactive)

    r = core.call_success("cmd_run", args)
    if r is None:
        print("Unknown command or argument(s): {}".format(in_args))
        sys.exit(1)
    return r


def main():
    main_main(sys.argv[1:])
