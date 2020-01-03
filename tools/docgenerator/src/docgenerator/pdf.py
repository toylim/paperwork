import cairo
import random

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from . import words



def generate(out_file):
    paper_size = Gtk.PaperSize.new("iso_a4")
    (w, h) = (
        paper_size.get_width(Gtk.Unit.POINTS),
        paper_size.get_height(Gtk.Unit.POINTS)
    )
    dictionary = words.WordDict()
    nb_pages = int(random.expovariate(1 / 500))

    print("Generating PDF {}...".format(out_file))
    with open(out_file, "wb") as fd:
        surface = cairo.PDFSurface(fd, w, h)
        context = cairo.Context(surface)

        for page_idx in range(0, nb_pages):
            print("Generating page {}/{}...".format(page_idx, nb_pages))
            words.draw_words(context, dictionary, w, h)
            context.show_page()

        surface.flush()
        surface.finish()
    print("PDF {} generated".format(out_file))
