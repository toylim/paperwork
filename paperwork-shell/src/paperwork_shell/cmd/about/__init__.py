import random

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
""".strip().split()  # to make copy and paste faster

COLORS = [
    '#0099ff',
    '#ff4400',
    '#00bd22',
    '#bf00ff',
]


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
        parser.add_parser(
            'about', help=_("About Paperwork")
        )

    def cmd_run(self, args):
        if args.command != 'about':
            return None

        self._show_logo()

        fonts = self._get_available_fonts()

        paperwork = [
            (
                '',
                _('Version: ') + self.core.call_success("app_get_version"),
                -1,
            ),
            (
                '',
                _("Because sorting documents is a machine's job."),
                -1,
            )
        ]
        self._show_section(
            "Paperwork", paperwork, fonts, color="#abcdef", size=28, skew=5
        )
        for x in range(0, 7):
            print("")

        sections = {}
        self.core.call_all("authors_get", sections)
        sections = [x for x in sections.items()]
        sections.sort(key=lambda x: x[0].lower())

        for (k, v) in sections:
            if len(v) <= 0:
                continue
            for x in range(0, 7):
                print("")
            self._show_section(k, v, fonts)

        print()
        print()

    def _get_available_fonts(self):
        all_fonts = fabulous.text.get_font_files()
        all_fonts = {n for n in all_fonts.keys()}

        out = []
        for font in VALIDATED_FONTS:
            if font not in all_fonts:
                continue
            out.append(font)
        return out

    def _show_logo(self):
        logo = self.core.call_success(
            "resources_get_file",
            "paperwork_shell.cmd.about", "logo.png"
        )
        logo = self.core.call_success("fs_unsafe", logo)
        logo = fabulous.image.Image(logo, width=60)
        logo = logo.reduce(logo.convert())
        for line in logo:
            print((16 * " ") + line)

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

    def _show_section_title(
            self, section_name, authors, fonts, size, skew, color):
        if color is None:
            color = random.choice(COLORS)
        font = random.choice(fonts)

        words = section_name.split()
        for word in self._group_small_words(words):
            txt = fabulous.text.Text(
                word,
                skew=skew, color=color, font=font, fsize=size, shadow=False
            )
            for line in txt:
                print(line)

    def _show_section(
            self,
            section_name, authors, fonts, size=18, color=None, skew=None):
        self._show_section_title(
            section_name, authors, fonts, size, skew, color
        )
        print(section_name)
        for author in authors:
            txt = author[1]
            if author[2] > 0:
                txt += " ({})".format(author[2])
            print((8 * " ") + txt)
