#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2019  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
import shutil

import PIL
import PIL.Image

import openpaperwork_core

from .. import _


class AppendableImage(object):
    def __init__(self, width, expected_height):
        # When scanning, width is reliable.
        # However height is not reliable, and truncating an image is much
        # easier then increasing its size. --> we allocate a big image and will
        # truncate it when needed
        self.img = PIL.Image.new(
            "RGB", (width, 10 * expected_height)
        )
        self.width = width
        self.height = 0

    def append(self, chunk):
        assert(self.img.size[0] == chunk.size[0])
        self.img.paste(chunk, (0, self.height))
        self.height += chunk.size[1]

    def get_image(self, start_line=0, end_line=None):
        if end_line is None:
            end_line = self.height
        return self.img.crop((0, start_line, self.img.size[0], end_line))


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.img = None
        self.last_line_displayed = 0  # in pixels
        self.txt_line_height = 0  # in pixels
        self.terminal_size = (80, 25)
        self.doc_id = None
        self.doc_url = None
        self.doc_renderer = None
        self.page_hashes = {}

    def get_deps(self):
        return [
            # if there are no doc_renderer loaded, nothing it displayed, which
            # may be fine.
            #
            # (see paperwork-json)
            # {
            #     'interface': 'doc_renderer',
            #     'defaults': [],
            # },
            {
                'interface': 'img_renderer',
                'defaults': ['paperwork_shell.display.docrendering.img'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def on_scan_feed_start(self, scan_id):
        self.core.call_all("shell_show_progress", False)

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        print()
        print(
            _("Scanning page {} (expected size: {}x{}) ...").format(
                page_nb + 1, scan_params.get_width(), scan_params.get_height()
            )
        )
        self.img = AppendableImage(
            scan_params.get_width(), scan_params.get_height()
        )
        self.last_line_displayed = 0

        # We need to figure out how many pixels one line of character will
        # represent.
        self.terminal_size = (
            # leave one character at the end of each line to make sure the
            # terminal doesn't add line return
            shutil.get_terminal_size()[0] - 1,
            shutil.get_terminal_size()[1]
        )
        ratio = scan_params.get_width() / self.terminal_size[0]
        # When Fabulous resizes an image to turn it into terminal characters,
        # it assumes that each characters is 1 pixel wide and 2 pixels high.
        self.txt_line_height = int(2 * ratio) + 1

    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        self.img.append(img_chunk)
        current_usable_line = (
            self.img.height - (self.img.height % self.txt_line_height)
        )
        if current_usable_line > self.last_line_displayed:
            img = self.img.get_image(
                self.last_line_displayed, current_usable_line
            )
            img = self.core.call_success(
                "img_render", img, terminal_width=self.terminal_size[0]
            )
            for line in img:
                print(line)
            self.last_line_displayed = current_usable_line

    def on_scan_page_end(self, scan_id, page_nb, img):
        img_size = img.size
        print(
            _("Page {} scanned (actual size: {}x{})").format(
                page_nb + 1, img_size[0], img_size[1]
            )
        )

    def on_scan_feed_end(self, scan_id):
        self.core.call_all("shell_show_progress", True)
        print()
        print(_("End of paper feed"))

    def on_scan2doc_start(self, scan_id, doc_id, doc_url):
        self.doc_id = doc_id
        self.doc_url = doc_url
        renderers = []
        self.core.call_all("doc_renderer_get", renderers)
        self.doc_renderer = renderers[-1]
        self.page_hashes = {}

    def _compute_page_hash(self, doc_url, page_idx):
        return self.core.call_success(
            "page_get_hash_by_url", doc_url, page_idx
        )

    def on_scan2doc_page_scanned(self, scan_id, doc_id, doc_url, page_idx):
        print(_("Page {} in document {} created").format(
            page_idx, doc_id
        ))
        self.page_hashes[page_idx] = self._compute_page_hash(
            self.doc_url, page_idx
        )

    def on_scan2doc_end(self, scan_id, doc_id, doc_url):
        self._show_last_page()
        self.doc_id = None
        self.doc_url = None
        self.doc_renderer = None

    def _show_last_page(self):
        if self.doc_renderer is None:
            return

        for page_idx in self.page_hashes:
            # we only want to display the page if something has actually
            # changed
            page_hash = self._compute_page_hash(self.doc_url, page_idx)
            if self.page_hashes[page_idx] == page_hash:
                continue
            self.page_hashes[page_idx] = page_hash

            lines = self.doc_renderer.get_preview_output(
                self.doc_id, self.doc_url, self.terminal_size, page_idx
            )
            print()
            for line in lines:
                print(line)
            print()

    def on_progress(self, upd_type, progress, description=None):
        self._show_last_page()
