import codecs
import random


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
