import os
import random
import subprocess
import sys

import fabulous.image
import fabulous.text

import openpaperwork_core

from ... import _


# XXX(Jflesch): crappy workaround for an unmaintained library ...
fabulous.image.basestring = str


VALIDATED_FONTS = """
comic
Comic_Sans_MS
Comic_Sans_MS_Bold
comicbd
LiberationMono-Bold
LiberationSans-Bold
times
timesbd
FreeMono
FreeMonoBold
FreeMonoBoldOblique
FreeMonoOblique
FreeSans
FreeSansBold
FreeSansBoldOblique
FreeSansOblique
FreeSerif
FreeSerifBold
FreeSerifBoldItalic
FreeSerifItalic
""".strip().split()  # to make copy and paste faster

COLORS = [
    '#0099ff',
    '#ff4400',
    '#00bd22',
    '#bf00ff',
]


class Paperwork(object):
    def __init__(self, core, fonts):
        self.core = core
        self.fonts = fonts

    def show(self, file=sys.stdout):
        nb_lines = 0

        logo = self.core.call_success(
            "resources_get_file",
            "paperwork_shell.cmd.about", "logo.png"
        )
        logo = self.core.call_success("fs_unsafe", logo)
        logo = fabulous.image.Image(logo, width=60)
        logo = logo.reduce(logo.convert())
        for line in logo:
            print(16 * " ", line, file=file, sep="")
            nb_lines += 1

        font = "FreeSans"
        if font not in self.fonts:
            font = self.fonts[0]

        txt = fabulous.text.Text(
            "Paperwork",
            skew=5, color="#abcdef", font=font, fsize=25, shadow=False
        )
        for line in txt:
            print(line, file=file)
            nb_lines += 1

        print("Paperwork", file=file)
        print(8 * " ",
              _('Version: ') + self.core.call_success("app_get_version"),
              file=file, sep="")
        print(8 * " ", _("Because sorting documents is a machine's job."),
              file=file, sep="")
        nb_lines += 3
        return nb_lines


class Section(object):
    def __init__(self, name, authors, fonts):
        self.name = name
        self.authors = authors
        self.fonts = fonts

    @staticmethod
    def _group_small_words(words):
        buf = []
        for word in words:
            buf.append(word)
            if len(word) > 3:
                yield " ".join(buf)
                buf = []
        if len(buf) > 0:
            yield " ".join(buf)

    def show(self, file=sys.stdout):
        nb_lines = 0
        color = random.choice(COLORS)
        font = random.choice(self.fonts)

        words = self.name.split()
        for word in self._group_small_words(words):
            txt = fabulous.text.Text(
                word, skew=0, color=color, font=font, fsize=18, shadow=False
            )
            for line in txt:
                print(line, file=file)
                nb_lines += 1

        print(self.name, file=file)
        nb_lines += 1
        for author in self.authors:
            txt = author[1]
            if author[2] > 0:
                txt += " ({})".format(author[2])
            print(8 * " ", txt, file=file, sep="")
            nb_lines += 1

        return nb_lines


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'app',
                'defaults': ['paperwork_backend.app'],
            },
            {
                'interface': 'authors',
                'defaults': ['paperwork_backend.authors'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        parser.add_parser('about', help=_("About Paperwork"))

    def cmd_run(self, args):
        if args.command != 'about':
            return None

        fonts = self._get_available_fonts()

        sections = {}
        self.core.call_all("authors_get", sections)
        sections = [x for x in sections.items()]
        sections.sort(key=lambda x: x[0].lower())

        sections = (
            [Paperwork(self.core, fonts)] +
            [Section(k, v, fonts) for (k, v) in sections if len(v) >= 0]
        )

        pager = os.environ.get('PAGER', 'less')
        try:
            pager = subprocess.Popen([pager, '-R'], universal_newlines=True,
                                     stdin=subprocess.PIPE, stdout=sys.stdout)
        except OSError:
            # Just output regularly, without a pager.
            output = sys.stdout
            pager = None
        else:
            output = pager.stdin

        try:
            for section in sections:
                section.show(file=output)
                if section != sections[-1]:
                    for x in range(0, 7):
                        print(file=output)
            print(file=output)
            print(file=output)
        finally:
            if pager is not None:
                pager.stdin.close()
                pager.wait()

    def _get_available_fonts(self):
        all_fonts = fabulous.text.get_font_files()
        all_fonts = {n for n in all_fonts.keys()}

        out = []
        for font in VALIDATED_FONTS:
            if font not in all_fonts:
                continue
            out.append(font)
        return out
