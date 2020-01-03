import random

import cairo

from . import words


def generate_img(core, paper_size, page_idx, nb_pages, dictionary=None):
    if dictionary is None:
        dictionary = words.WordDict()

    paper_size = (int(paper_size[0]) * 4, int(paper_size[1]) * 4)

    print("Generating image {}...".format(paper_size))
    surface = cairo.ImageSurface(
        cairo.Format.RGB24, paper_size[0], paper_size[1]
    )
    context = cairo.Context(surface)

    words.draw_words(
        context, dictionary, paper_size[0], paper_size[1],
        page_idx, nb_pages,
        word_height=20 * 4, word_space=10 * 4
    )

    surface.flush()
    print("Image generated")
    return surface


def generate(core, file_out, paper_size, page_idx=0, nb_pages=1):
    img = generate_img(core, paper_size, page_idx, nb_pages)
    img = core.call_success("cairo_surface_to_pillow", img)
    with core.call_success("fs_open", file_out, 'wb') as fd:
        img.save(fd, format="PNG")
