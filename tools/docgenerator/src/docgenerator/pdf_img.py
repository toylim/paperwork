import random

import cairo

from . import img
from . import words


def generate(core, out_file, paper_size, *args, **kwargs):
    dictionary = words.WordDict()
    nb_pages = int(random.expovariate(1 / 100))
    if nb_pages <= 0:
        nb_pages = 1
    if nb_pages > 500:
        nb_pages = 500

    print("Generating PDF with images only {}...".format(out_file))
    with core.call_success("fs_open", out_file, "wb") as fd:
        surface = cairo.PDFSurface(fd, int(paper_size[0]), int(paper_size[1]))
        context = cairo.Context(surface)

        for page_idx in range(0, nb_pages):
            print("Generating page {}/{}...".format(page_idx, nb_pages))
            img_surface = img.generate_img(
                core, paper_size, page_idx, nb_pages, dictionary=dictionary,
                jpeg=True
            )

            scale_factor = paper_size[0] / img_surface.get_width()

            context.save()
            try:
                context.identity_matrix()
                context.scale(scale_factor, scale_factor)
                context.set_source_surface(img_surface)
                context.paint()
            finally:
                context.restore()

            context.show_page()

        surface.flush()
        surface.finish()
    print("PDF with images only {} generated".format(out_file))
