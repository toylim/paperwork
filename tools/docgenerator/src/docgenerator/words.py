import codecs
import random

import gi
gi.require_version('PangoCairo', '1.0')
from gi.repository import PangoCairo


WORD_HEIGHT = 20
WORD_SPACE = 10


def draw_words(context, words, width, height):
    w = WORD_SPACE
    h = WORD_SPACE

    context.save()
    try:
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.rectangle(0, 0, width, height)
        context.fill()
    finally:
        context.restore()

    while True:
        word = words.pick_word()

        layout = PangoCairo.create_layout(context)
        layout.set_text(word, -1)
        layout_size = layout.get_size()

        txt_factor = WORD_HEIGHT / layout_size[1]
        word_h = WORD_HEIGHT
        word_w = layout_size[0] * txt_factor

        if w + word_w >= width:
            h += word_h + WORD_SPACE
            w = WORD_SPACE
        if h >= height:
            return

        context.save()
        try:
            context.set_source_rgb(0, 0, 0)
            context.translate(w, h)
            PangoCairo.update_layout(context, layout)
            PangoCairo.show_layout(context, layout)
        finally:
            context.restore()

        w += word_w + WORD_SPACE


class WordDict(object):
    DICTIONARY = "/usr/share/dict/words"

    def __init__(self):
        print("Loading {} ...".format(self.DICTIONARY))
        self.dictionary = []  # length --> words
        with codecs.open(self.DICTIONARY, 'r', encoding='utf-8') as file_desc:
            for word in file_desc:
                word = word.strip()
                self.dictionary.append(word)
        print("Dictionnary loaded")

    def pick_word(self):
        return self.dictionary[random.randint(0, len(self.dictionary) - 1)]
