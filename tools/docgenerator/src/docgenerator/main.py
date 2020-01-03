import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import openpaperwork_core
import paperwork_backend
import paperwork_shell.main

from . import img
from . import pdf


DOC_GENERATORS = {
    'pdf': pdf.generate,
    'img': img.generate,
    # 'pdf_img': pdf_img.generate,
}


def main_generate_one():
    if len(sys.argv) <= 2:
        print("Usage:")
        print("  {} <type> <out_file>".format(sys.argv[0]))
        sys.exit(1)

    core = openpaperwork_core.Core()
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()

    core.load('openpaperwork_core.log_print')
    core.call_all("set_log_output", sys.stderr)
    core.call_all("set_log_level", 'debug')
    core.init()

    core.call_all(
        "config_load", "paperwork2", "docgenerator",
        paperwork_shell.main.DEFAULT_CLI_PLUGINS
    )

    paper_size = Gtk.PaperSize.new("iso_a4")
    paper_size = (
        paper_size.get_width(Gtk.Unit.POINTS),
        paper_size.get_height(Gtk.Unit.POINTS)
    )

    DOC_GENERATORS[sys.argv[1]](core, sys.argv[2], paper_size)
