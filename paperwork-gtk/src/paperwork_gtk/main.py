import argparse
import logging
import gettext
import sys

import openpaperwork_core

import paperwork_backend


_ = gettext.gettext

LOGGER = logging.getLogger(__name__)

DEFAULT_GUI_PLUGINS = paperwork_backend.DEFAULT_PLUGINS + [
    'openpaperwork_core.resources.setuptools',
    'openpaperwork_core.spatial.rtree',
    'openpaperwork_gtk.mainloop.glib',
    'openpaperwork_gtk.pixbuf.pillow',
    'openpaperwork_gtk.resources',
    'paperwork_backend.guesswork.cropping.calibration',
    'paperwork_gtk.actions.doc_delete',
    'paperwork_gtk.actions.doc_properties',
    'paperwork_gtk.busy.mouse',
    'paperwork_gtk.cmd.install',
    'paperwork_gtk.drawer.calibration',
    'paperwork_gtk.drawer.frame',
    'paperwork_gtk.drawer.pillow',
    'paperwork_gtk.drawer.scan',
    'paperwork_gtk.gesture.zoom',
    'paperwork_gtk.keyboard_shortcut.zoom',
    'paperwork_gtk.mainwindow.doclist',
    'paperwork_gtk.mainwindow.doclist.labeler',
    'paperwork_gtk.mainwindow.doclist.name',
    'paperwork_gtk.mainwindow.doclist.thumbnailer',
    'paperwork_gtk.mainwindow.docproperties',
    'paperwork_gtk.mainwindow.docproperties.labels',
    'paperwork_gtk.mainwindow.docproperties.name',
    'paperwork_gtk.mainwindow.docview',
    'paperwork_gtk.mainwindow.docview.controllers.click',
    'paperwork_gtk.mainwindow.docview.controllers.layout',
    'paperwork_gtk.mainwindow.docview.controllers.page_number',
    'paperwork_gtk.mainwindow.docview.controllers.scroll',
    'paperwork_gtk.mainwindow.docview.controllers.zoom',
    'paperwork_gtk.mainwindow.docview.pageadd.buttons',
    'paperwork_gtk.mainwindow.docview.pageadd.import',
    'paperwork_gtk.mainwindow.docview.pageadd.scan',
    'paperwork_gtk.mainwindow.docview.pageadd.source_popover',
    'paperwork_gtk.mainwindow.docview.pageinfo',
    'paperwork_gtk.mainwindow.docview.pageinfo.layout_settings',
    'paperwork_gtk.mainwindow.docview.pageprocessing',
    'paperwork_gtk.mainwindow.docview.pageview',
    'paperwork_gtk.mainwindow.docview.pageview.boxes',
    'paperwork_gtk.mainwindow.docview.pageview.boxes.all',
    'paperwork_gtk.mainwindow.docview.pageview.boxes.hover',
    'paperwork_gtk.mainwindow.docview.pageview.boxes.selection',
    'paperwork_gtk.mainwindow.docview.pageview.boxes.search',
    'paperwork_gtk.mainwindow.docview.scanview',
    'paperwork_gtk.mainwindow.progress',
    'paperwork_gtk.mainwindow.search.field',
    'paperwork_gtk.mainwindow.window',
    'paperwork_gtk.new_doc',
    'paperwork_gtk.readonly',
    'paperwork_gtk.settings',
    'paperwork_gtk.settings.ocr.settings',
    'paperwork_gtk.settings.ocr.selector_popover',
    'paperwork_gtk.settings.scanner.calibration',
    'paperwork_gtk.settings.scanner.dev_id_popover',
    'paperwork_gtk.settings.scanner.mode_popover',
    'paperwork_gtk.settings.scanner.resolution_popover',
    'paperwork_gtk.settings.scanner.settings',
    'paperwork_gtk.settings.stats',
    'paperwork_gtk.settings.storage',
    'paperwork_gtk.widget.flowlayout',
    'paperwork_gtk.widget.label',
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

        LOGGER.info("Starting synchronization ...")
        promises = []
        core.call_all("sync", promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        core.call_one("mainloop_schedule", promise.schedule)

        LOGGER.info("Ready")
        core.call_one("mainloop", halt_on_uncatched_exception=False)
        LOGGER.info("Quitting")
        core.call_all("on_quit")

    else:

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help=_('command'), dest='command', required=True
        )

        core.call_all("cmd_complete_argparse", cmd_parser)
        args = parser.parse_args(in_args)

        core.call_all("cmd_set_interactive", True)

        r = core.call_all("cmd_run", args)
        if r <= 0:
            print("Unknown command or argument(s): {}".format(in_args))
            sys.exit(1)
        core.call_all("on_quit")
        return r


def main():
    main_main(sys.argv[1:])
