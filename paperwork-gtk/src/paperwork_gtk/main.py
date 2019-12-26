import argparse
import logging
import gettext
import sys

import openpaperwork_core

import paperwork_backend


_ = gettext.gettext

LOGGER = logging.getLogger(__name__)

DEFAULT_GUI_PLUGINS = paperwork_backend.DEFAULT_PLUGINS + [
    'openpaperwork_core.log_collector',
    'openpaperwork_core.resources.setuptools',
    'openpaperwork_gtk.resources',
    'paperwork_gtk.mainwindow.doclist',
    'paperwork_gtk.mainwindow.window',
]


def main_main(in_args):
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin log_print first.

    core = openpaperwork_core.Core()
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()

    core.load('openpaperwork_core.log_collector')
    core.init()

    core.call_all(
        "config_load", "paperwork2", "paperwork-gtk", DEFAULT_GUI_PLUGINS
    )

    if len(in_args) <= 0:

        core.call_all("on_initialized")
        LOGGER.info("Ready")
        core.call_one("mainloop", halt_on_uncatched_exception=False)
        LOGGER.info("Quitting")

    else:

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help=_('command'), dest='command', required=True
        )

        core.call_all("cmd_complete_argparse", cmd_parser)
        args = parser.parse_args(in_args)

        core.call_all("cmd_set_interactive", True)

        r = core.call_success("cmd_run", args)
        if r is None:
            print("Unknown command or argument(s): {}".format(in_args))
            sys.exit(1)
        return r


def main():
    main_main(sys.argv[1:])
