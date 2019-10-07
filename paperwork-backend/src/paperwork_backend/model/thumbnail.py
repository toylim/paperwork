#!/usr/bin/python3

import logging
import time

import PIL.Image

import openpaperwork_core
import openpaperwork_core.promise

from . import util


THUMBNAIL_WIDTH = 64
THUMBNAIL_HEIGHT = 80

PAGE_THUMBNAIL_FILENAME = 'paper.{}.thumb.jpg'

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'pages',
            'thumbnail',
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('page_img', [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ]),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ])
            ]
        }

    def thumbnail_get_doc(self, doc_url):
        return self.thumbnail_get_page(doc_url, page_idx=0)

    def thumbnail_get_doc_promise(self, doc_url):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_doc, args=(doc_url,)
        )

    def thumbnail_get_page(self, doc_url, page_idx):
        thumbnail_url = self.core.call_success(
            "fs_join", doc_url, PAGE_THUMBNAIL_FILENAME.format(page_idx + 1)
        )
        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )

        if self.core.call_success("fs_exists", thumbnail_url) is not None:
            thumbnail_mtime = self.core.call_success(
                "fs_get_mtime", thumbnail_url
            )
            if not self.core.call_success("fs_iswritable", thumbnail_url):
                page_mtime = self.core.call_success("fs_get_mtime", page_url)
                if thumbnail_mtime < page_mtime:
                    self.core.call_all("fs_unlink", thumbnail_url)

        if self.core.call_success("fs_exists", thumbnail_url) is not None:
            LOGGER.debug("Loading thumbnail for %s page %d", doc_url, page_idx)
            return self.core.call_success("url_to_pillow", thumbnail_url)

        LOGGER.info("Generating thumbnail for %s page %d", doc_url, page_idx)
        start = time.time()
        page = self.core.call_success("url_to_pillow", page_url)

        (width, height) = page.size
        scale = max(
            float(width) / THUMBNAIL_WIDTH,
            float(height) / THUMBNAIL_HEIGHT
        )
        width /= scale
        height /= scale
        thumbnail = page.resize((int(width), int(height)), PIL.Image.ANTIALIAS)

        self.core.call_success(
            "pillow_to_url", thumbnail, thumbnail_url,
            format='JPEG', quality=0.85
        )

        stop = time.time()
        LOGGER.info(
            "Thumbnail for %s page %d generated in %f seconds",
            doc_url, page_idx, stop - start
        )
        return thumbnail

    def thumbnail_get_page_promise(self, doc_url, page_idx):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_page, args=(doc_url, page_idx)
        )

    def page_delete_by_url(self, doc_url, page_idx):
        return util.delete_page_file(
            self.core, PAGE_THUMBNAIL_FILENAME, doc_url, page_idx
        )

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        return util.move_page_file(
            self.core, PAGE_THUMBNAIL_FILENAME,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        )
