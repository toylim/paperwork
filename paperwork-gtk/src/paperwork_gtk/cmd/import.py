import logging

import openpaperwork_core

from .. import _

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_doc_import',
                'defaults': ['paperwork_gtk.docimport'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser('import', help=_(
            "Run Paperwork and import files passed as arguments into a new "
            "document"
        ))
        p.add_argument("files", metavar="URLS", type=str, nargs="*", help=_(
            "URLs or paths of files to import"
        ))

    def cmd_run(self, args):
        if args.command != 'import':
            return None

        self.core.call_all("on_initialized")

        # when no file is specified, we still start the GUI, because the
        # desktop file always calls paperwork-gtk import (see install.py for
        # the rationale).
        if args.files:
            files = [self.core.call_success("fs_safe", f) for f in args.files]
            LOGGER.info("Scheduling import for files %s", " ".join(files))
            self.core.call_one(
                "mainloop_schedule",
                self.core.call_all, "gtk_doc_import", files
            )
        LOGGER.info("Ready")
        self.core.call_one("mainloop", halt_on_uncaught_exception=False)
        LOGGER.info("Quitting")
        self.core.call_all("config_save")
        self.core.call_all("on_quit")
        return True
