#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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

from copy import copy
import logging
import os
import os.path
import tempfile

import PIL.Image

from ..common.export import Exporter
from ..common.export import dummy_export_progress_cb
from ..util import strip_accents
from ..util import split_words

logger = logging.getLogger(__name__)


class PageExporter(Exporter):
    def __init__(self, page, img_format='PNG', mime='image/png',
                 valid_exts=['png']):
        super().__init__(page, img_format)
        self.can_change_quality = True
        self.can_select_format = False
        self.page = page
        self.img_format = img_format
        self.mime = mime
        self.valid_exts = valid_exts
        self.__quality = 75
        self.__img = None
        self.__postprocess_func = None

    def get_mime_type(self):
        return self.mime

    def get_file_extensions(self):
        return self.valid_exts

    def save(self, target_path, progress_cb=dummy_export_progress_cb):
        target_path = self.page.fs.safe(target_path)

        progress_cb(0, 4)

        # the user gives us a quality between 0 and 100
        # but PIL expects a quality between 1 and 75
        quality = int(float(self.__quality) / 100.0 * 74.0) + 1
        # We also adjust the size of the image
        resize_factor = float(self.__quality) / 100.0

        img = self.page.img
        img.load()
        progress_cb(1, 4)

        new_size = (int(resize_factor * img.size[0]),
                    int(resize_factor * img.size[1]))
        img = img.resize(new_size, PIL.Image.ANTIALIAS)
        progress_cb(2, 4)

        if self.__postprocess_func:
            img = self.__postprocess_func(img)
            progress_cb(3, 4)

        with self.page.fs.open(target_path, 'wb') as fd:
            img.save(fd, self.img_format, quality=quality)
        progress_cb(4, 4)

        return target_path

    def refresh(self):
        (tmpfd, tmppath) = tempfile.mkstemp(
            suffix=".jpg",
            prefix="paperwork_export_"
        )
        os.close(tmpfd)

        path = self.save(tmppath)
        with self.page.fs.open(path, 'rb') as fd:
            img = PIL.Image.open(fd)
            img.load()

        self.__img = (path, img)

    def set_quality(self, quality):
        self.__quality = int(quality)
        self.__img = None

    def set_postprocess_func(self, postprocess_func):
        self.__postprocess_func = postprocess_func
        self.__img = None

    def estimate_size(self):
        if self.__img is None:
            self.refresh()
        return self.page.fs.getsize(self.__img[0])

    def get_img(self):
        if self.__img is None:
            self.refresh()
        return self.__img[1]

    def __str__(self):
        return self.img_format

    def __repr__(self):
        return str(self)

    def __copy__(self):
        return PageExporter(self.page, self.img_format, self.mime,
                            self.valid_exts)


class BasicPage(object):

    # The width of the thumbnails is defined arbitrarily
    DEFAULT_THUMB_WIDTH = 150
    # The height of the thumbnails is defined based on the A4 format
    # proportions
    DEFAULT_THUMB_HEIGHT = 212

    EXT_THUMB = "thumb.jpg"
    EXT_BOX = "words"
    FILE_PREFIX = "paper."

    boxes = []
    img = None
    size = (0, 0)

    can_edit = False

    PAGE_ID_SEPARATOR = "|"

    def __init__(self, doc, page_nb):
        """
        Don't create directly. Please use ImgDoc.get_page()
        """
        self.fs = doc.fs
        self.doc = doc
        self.page_nb = page_nb

        assert(self.page_nb >= 0)
        self.__prototype_exporters = {
            'PNG': PageExporter(self, 'PNG', 'image/png', ["png"]),
            'JPEG': PageExporter(self, 'JPEG', 'image/jpeg', ["jpeg", "jpg"]),
        }

    def __get_pageid(self):
        return self.doc.docid + self.PAGE_ID_SEPARATOR + str(self.page_nb)

    pageid = property(__get_pageid)
    id = property(__get_pageid)

    def _get_filepath(self, ext):
        """
        Returns a file path relative to this page
        """
        filename = ("%s%d.%s" % (self.FILE_PREFIX, self.page_nb + 1, ext))
        return self.fs.join(self.doc.path, filename)

    def __make_thumbnail(self, width, height):
        """
        Create the page's thumbnail
        """
        (w, h) = self.size
        factor = max(
            (float(w) / width),
            (float(h) / height)
        )
        w /= factor
        h /= factor
        return self.get_image((round(w), round(h)))

    def _get_thumb_path(self):
        return self._get_filepath(self.EXT_THUMB)

    def get_thumbnail(self, width, height):
        """
        thumbnail with a memory cache
        """
        # get from the file
        thumb_path = self._get_thumb_path()
        try:
            doc_file_path = self.get_doc_file_path()

            if (self.fs.exists(thumb_path) and
                    (self.fs.getmtime(doc_file_path) <
                        self.fs.getmtime(thumb_path) or not
                        self.fs.writable(thumb_path))):
                with self.fs.open(thumb_path, 'rb') as fd:
                    thumbnail = PIL.Image.open(fd)
                    thumbnail.load()
                if thumbnail.size[0] == width or thumbnail.size[1] == height:
                    # fills the specified area
                    return thumbnail
                logger.warning(
                    "[%s] Unexpected thumbnail size: %s instead of %s ;"
                    " Updating thumbnail ...",
                    str(self.doc.docid), str(thumbnail.size),
                    str((width, height))
                )
        except Exception as exc:
            logger.warning(
                "[%s] Failed to check doc and thumbnail mdate. Forcing update"
                " of the thumbnail", str(self.doc.docid), exc_info=exc
            )

        logger.info("[%s] Updating thumbnail ...", str(self.doc.docid))
        thumbnail = self.__make_thumbnail(width, height)
        with self.fs.open(thumb_path, 'wb') as fd:
            thumbnail.save(fd, format="JPEG")

        return thumbnail

    def __get_text(self):
        return self._get_text()

    text = property(__get_text)

    def print_page_cb(self, print_op, print_context, keep_refs={}):
        raise NotImplementedError()

    def destroy(self):
        raise NotImplementedError()

    def get_export_formats(self):
        return self.__prototype_exporters.keys()

    def build_exporter(self, file_format='PNG', preview_page_nb=0):
        """
        Arguments:
            preview_page_nb: Juste here for consistency with
                doc.build_exporter()
        """
        return copy(self.__prototype_exporters[file_format.upper()])

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __repr__(self):
        return str(self)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if other is None:
            return False
        return self.doc == other.doc and self.page_nb == other.page_nb

    def __contains__(self, sentence):
        words = split_words(sentence, keep_short=True)
        txt = self.text
        for line in txt:
            line = strip_accents(line.lower())
            for word in words:
                if word in line:
                    return True
        return False

    def __get_keywords(self):
        """
        Get all the keywords related of this page

        Returns:
            An array of strings
        """
        txt = self.text
        for line in txt:
            for word in split_words(line):
                yield(word)

    keywords = property(__get_keywords)

    def has_ocr(self):
        return self.fs.exists(self._get_filepath(self.EXT_BOX))

    def __hash__(self):
        return hash(self.pageid)


class DummyPage(object):
    pageid = 0
    page_nb = -1
    text = ""
    boxes = []
    keywords = []
    img = None

    def __init__(self, parent_doc):
        self.doc = parent_doc

    def _get_filepath(self, ext):
        raise NotImplementedError()

    def get_thumbnail(self, width):
        raise NotImplementedError()

    def print_page_cb(self, print_op, print_context):
        raise NotImplementedError()

    def destroy(self):
        pass

    def get_image(self, size):
        return None

    def get_boxes(self, sentence):
        return []

    def get_export_formats(self):
        return []

    def build_exporter(self, file_format='PNG'):
        raise NotImplementedError()

    def has_ocr(self):
        return False

    def __str__(self):
        return "Dummy page"

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return 0
