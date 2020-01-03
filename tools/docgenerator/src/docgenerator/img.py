import random

import cairo

from . import words


def generate_img(core, paper_size):
    dictionary = words.WordDict()
    nb_pages = int(random.expovariate(1 / 500))

    paper_size = (int(paper_size[0]) * 4, int(paper_size[1]) * 4)

    print("Generating image {}...".format(paper_size))
    surface = cairo.ImageSurface(
        cairo.Format.RGB24, paper_size[0], paper_size[1]
    )
    context = cairo.Context(surface)

    words.draw_words(
        context, dictionary, paper_size[0], paper_size[1]
    )

    surface.flush()
    print("Image generated")
    return core.call_success("cairo_surface_to_pillow", surface)


def generate(core, file_out, paper_size):
    img = generate_img(core, paper_size)
    img.save(file_out)
