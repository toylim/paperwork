import argparse
import gettext
import json
import sys
import traceback

import openpaperwork_core

import paperwork_backend


_ = gettext.gettext

DEFAULT_SHELL_PLUGINS = paperwork_backend.DEFAULT_PLUGINS + [
    'openpaperwork_core.log_print',
    'openpaperwork_core.mainloop.asyncio',
    'paperwork_shell.cmd.delete',
    'paperwork_shell.cmd.edit',
    'paperwork_shell.cmd.export',
    'paperwork_shell.cmd.extra_text',
    'paperwork_shell.cmd.import',
    'paperwork_shell.cmd.label',
    'paperwork_shell.cmd.move',
    'paperwork_shell.cmd.ocr',
    'paperwork_shell.cmd.rename',
    'paperwork_shell.cmd.reset',
    'paperwork_shell.cmd.scan',
    'paperwork_shell.cmd.scanner',
    'paperwork_shell.cmd.search',
    'paperwork_shell.cmd.show',
    'paperwork_shell.cmd.sync',
]

DEFAULT_CLI_PLUGINS = DEFAULT_SHELL_PLUGINS + [
    "paperwork_shell.display.docrendering.extra_text",
    "paperwork_shell.display.docrendering.img",
    "paperwork_shell.display.docrendering.labels",
    "paperwork_shell.display.docrendering.text",
    'paperwork_shell.display.progress',
    "paperwork_shell.display.scan",
]
DEFAULT_JSON_PLUGINS = DEFAULT_SHELL_PLUGINS


def main_main(in_args, application_name, default_plugins, interactive):
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin log_print first.

    core = openpaperwork_core.Core()
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()

    core.load('openpaperwork_core.log_print')
    core.init()
    core.call_all("set_log_output", sys.stderr)
    core.call_all("set_log_level", 'warning')

    core.call_all(
        "config_load", "paperwork2", application_name, default_plugins
    )

    parser = argparse.ArgumentParser()
    cmd_parser = parser.add_subparsers(
        help=_('command'), dest='command', required=True
    )

    core.call_all("cmd_complete_argparse", cmd_parser)
    args = parser.parse_args(in_args)

    core.call_all("cmd_set_interactive", interactive)

    r = core.call_all("cmd_run", args)
    if r <= 0:
        print("Unknown command or argument(s): {}".format(in_args))
        sys.exit(1)

    core.call_all("on_quit")
    return r


def json_main():
    try:
        r = main_main(
            sys.argv[1:], 'paperwork-json', DEFAULT_JSON_PLUGINS,
            interactive=False
        )
        print(json.dumps(
            r,
            indent=4,
            separators=(',', ': '),
            sort_keys=True
        ))
    except Exception as exc:
        stack = traceback.format_exc().splitlines()
        print(json.dumps(
            {
                "status": "error",
                "exception": str(type(exc)),
                "args": str(exc.args),
                "reason": str(exc),
                "stack": stack,
            },
            indent=4,
            separators=(',', ': '),
            sort_keys=True
        ))
        sys.exit(2)


def cli_main():
    main_main(
        sys.argv[1:], 'paperwork-cli', DEFAULT_CLI_PLUGINS, interactive=True
    )