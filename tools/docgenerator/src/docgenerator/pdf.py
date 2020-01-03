import random

import cairo

from . import words



def generate(core, out_file, paper_size):
    dictionary = words.WordDict()
    nb_pages = int(random.expovariate(1 / 500))
    if nb_pages > 2000:
        nb_pages = 2000

    print("Generating PDF {}...".format(out_file))
    with core.call_success("fs_open", out_file, "wb") as fd:
        surface = cairo.PDFSurface(fd, int(paper_size[0]), int(paper_size[1]))
        context = cairo.Context(surface)

        for page_idx in range(0, nb_pages):
            print("Generating page {}/{}...".format(page_idx, nb_pages))
            words.draw_words(
                context, dictionary,
                int(paper_size[0]), int(paper_size[1]),
                page_idx, nb_pages
            )
            context.show_page()

        surface.flush()
        surface.finish()
    print("PDF {} generated".format(out_file))
