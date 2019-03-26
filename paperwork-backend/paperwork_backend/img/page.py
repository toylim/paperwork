#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
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

"""
Code relative to page handling.
"""

import logging
import re

import PIL.Image
import pyocr
import pyocr.builders

from ..common.page import BasicPage
from ..util import image2surface


logger = logging.getLogger(__name__)


class ImgPage(BasicPage):

    """
    Represents a page. A page is a sub-element of ImgDoc.
    """

    EXT_IMG = "jpg"
    KEYWORD_HIGHLIGHT = 3
    FILE_REGEX = re.compile(
        re.escape(BasicPage.FILE_PREFIX) + r"[1-9][0-9]*\." + EXT_IMG,
        re.IGNORECASE
    )

    can_edit = True

    def __init__(self, doc, page_nb=None):
        if page_nb is None:
            page_nb = doc.nb_pages
        BasicPage.__init__(self, doc, page_nb)

    def __get_box_path(self):
        """
        Returns the file path of the box list corresponding to this page
        """
        return self._get_filepath(self.EXT_BOX)

    __box_path = property(__get_box_path)

    def __get_img_path(self):
        """
        Returns the file path of the image corresponding to this page
        """
        return self._get_filepath(self.EXT_IMG)

    def get_doc_file_path(self):
        """
        Returns the file path of the image corresponding to this page
        """
        return self.__get_img_path()

    __img_path = property(__get_img_path)

    def __get_last_mod(self):
        try:
            return self.fs.getmtime(self.__get_box_path())
        except OSError:
            return 0.0

    last_mod = property(__get_last_mod)

    def _get_text(self):
        """
        Get the text corresponding to this page
        """
        boxes = self.boxes
        txt = []
        for line in boxes:
            txt_line = u""
            for box in line.word_boxes:
                txt_line += u" " + box.content
            txt.append(txt_line)
        return txt

    def __get_boxes(self):
        """
        Get all the word boxes of this page.
        """
        boxfile = self.__box_path

        try:
            box_builder = pyocr.builders.LineBoxBuilder()
            with self.fs.open(boxfile, 'r') as file_desc:
                boxes = box_builder.read_file(file_desc)
            if boxes != []:
                return boxes
            # fallback: old format: word boxes
            # shouldn't be used anymore ...
            box_builder = pyocr.builders.WordBoxBuilder()
            with self.fs.open(boxfile, 'r') as file_desc:
                boxes = box_builder.read_file(file_desc)
            if len(boxes) <= 0:
                return []
            logger.warning("WARNING: Doc %s uses old box format" %
                           (str(self.doc)))
            return [pyocr.builders.LineBox(boxes, boxes[0].position)]
        except IOError as exc:
            logger.error("Unable to get boxes for '%s': %s"
                         % (self.doc.docid, exc))
            return []

    def __set_boxes(self, boxes):
        boxfile = self.__box_path
        with self.fs.open(boxfile, 'w') as file_desc:
            pyocr.builders.LineBoxBuilder().write_file(file_desc, boxes)

    boxes = property(__get_boxes, __set_boxes)

    def __get_img(self):
        """
        Returns an image object corresponding to the page
        """
        with self.fs.open(self.__img_path, 'rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            return img

    def __set_img(self, img):
        with self.fs.open(self.__img_path, 'wb') as fd:
            img = img.convert("RGB")
            img.save(fd, format="JPEG")

    img = property(__get_img, __set_img)

    def get_image(self, size):
        img = self.img
        return img.resize(size, PIL.Image.ANTIALIAS)

    def __get_size(self):
        with self.fs.open(self.__img_path, 'rb') as fd:
            img = PIL.Image.open(fd)
            return img.size

    size = property(__get_size)

    ORIENTATION_PORTRAIT = 0
    ORIENTATION_LANDSCAPE = 1

    def print_page_cb(self, print_op, print_context, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        scaling = 2.0

        img = self.img
        (width, height) = img.size

        # take care of rotating the image if required
        if print_context.get_width() <= print_context.get_height():
            print_orientation = self.ORIENTATION_PORTRAIT
        else:
            print_orientation = self.ORIENTATION_LANDSCAPE
        if width <= height:
            img_orientation = self.ORIENTATION_PORTRAIT
        else:
            img_orientation = self.ORIENTATION_LANDSCAPE
        if print_orientation != img_orientation:
            logger.info("Rotating the page ...")
            img = img.rotate(90, expand=True)

        (width, height) = img.size

        # scale the image down
        # XXX(Jflesch): beware that we get floats for the page size ...
        scaling = min(
            print_context.get_width() / width,
            print_context.get_height() / height
        )

        logger.info("DPI: %fx%f" % (print_context.get_dpi_x(),
                                    print_context.get_dpi_y()))

        surface = image2surface(img)
        keep_refs['surface_cache_' + str(self.page_nb)] = surface

        # .. and print !
        cairo_context = print_context.get_cairo_context()
        cairo_context.scale(scaling, scaling)
        cairo_context.set_source_surface(surface, 0, 0)
        cairo_context.paint()

    def change_index(self, offset=0):
        """
        Move the page number by a given offset. Beware to not let any hole
        in the page numbers when doing this. Make sure also that the wanted
        number is available.
        Will also change the page number of the current object.
        """
        src = {}
        src["box"] = self.__get_box_path()
        src["img"] = self.__get_img_path()
        src["thumb"] = self._get_thumb_path()

        page_nb = self.page_nb

        page_nb += offset

        logger.info("--> Moving page %d (+%d) to index %d"
                    % (self.page_nb, offset, page_nb))

        self.page_nb = page_nb

        dst = {}
        dst["box"] = self.__get_box_path()
        dst["img"] = self.__get_img_path()
        dst["thumb"] = self._get_thumb_path()

        for key in src.keys():
            if self.fs.exists(src[key]):
                if self.fs.exists(dst[key]):
                    logger.error("Error: file already exists: %s" % dst[key])
                    assert(0)
                self.fs.rename(src[key], dst[key])

    def destroy(self):
        """
        Delete the page. May delete the whole document if it's actually the
        last page.
        """
        logger.info("Destroying page: %s" % self)
        if self.doc.nb_pages <= 1:
            self.doc.destroy()
            return
        doc_pages = self.doc.pages[:]
        current_doc_nb_pages = self.doc.nb_pages
        paths = [
            self.__get_box_path(),
            self.__get_img_path(),
            self._get_thumb_path(),
        ]
        for path in paths:
            if self.fs.exists(path):
                self.fs.unlink(path)
        for page_nb in range(self.page_nb + 1, current_doc_nb_pages):
            page = doc_pages[page_nb]
            page.change_index(offset=-1)

    def _steal_content(self, other_page):
        """
        Call ImgDoc.steal_page() instead
        """
        other_doc = other_page.doc
        other_doc_pages = other_doc.pages[:]
        other_doc_nb_pages = other_doc.nb_pages
        other_page_nb = other_page.page_nb

        to_move = [
            (other_page.__get_box_path(), self.__get_box_path()),
            (other_page.__get_img_path(), self.__get_img_path()),
            (other_page._get_thumb_path(), self._get_thumb_path())
        ]
        for (src, dst) in to_move:
            # sanity check
            if self.fs.exists(dst):
                logger.error("Error, file already exists: %s" % dst)
                assert(0)
        for (src, dst) in to_move:
            logger.info("%s --> %s" % (src, dst))
            self.fs.rename(src, dst)

        if (other_doc_nb_pages <= 1):
            other_doc.destroy()
        else:
            for page_nb in range(other_page_nb + 1, other_doc_nb_pages):
                page = other_doc_pages[page_nb]
                page.change_index(offset=-1)

    def get_docfilehash(self):
        return self.doc.hash_file(self.fs, self.__get_img_path())

    def has_ocr(self):
        # always act as if images have OCR file attached
        return True
