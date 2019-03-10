#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
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

import io
import logging

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Libinsane
import PIL.ImageDraw


logger = logging.getLogger(__name__)


def add_img_border(img, color="#a6a5a4", width=1):
    """
    Add a border of the specified color and width around a PIL image
    """
    img_draw = PIL.ImageDraw.Draw(img)
    for line in range(0, width):
        img_draw.rectangle([(line, line), (img.size[0]-1-line,
                                           img.size[1]-1-line)],
                           outline=color)
    del img_draw
    return img


def image2pixbuf(img):
    """
    Convert an image object to a gdk pixbuf
    """
    if img is None:
        return None
    img = img.convert("RGB")

    if hasattr(GdkPixbuf.Pixbuf, 'new_from_bytes'):
        data = GLib.Bytes.new(img.tobytes())
        (width, height) = img.size
        return GdkPixbuf.Pixbuf.new_from_bytes(
            data, GdkPixbuf.Colorspace.RGB, False, 8, width, height, width * 3
        )

    file_desc = io.BytesIO()
    try:
        img.save(file_desc, "ppm")
        contents = file_desc.getvalue()
    finally:
        file_desc.close()
    loader = GdkPixbuf.PixbufLoader.new_with_type("pnm")
    try:
        loader.write(contents)
        pixbuf = loader.get_pixbuf()
    finally:
        loader.close()
    return pixbuf


def raw2pixbuf(img_bytes, params):
    nb_bytes = len(img_bytes)
    img_bytes = GLib.Bytes.new(img_bytes)
    fmt = params.get_format()
    assert(fmt == Libinsane.ImgFormat.RAW_RGB_24)
    (w, h) = (
        params.get_width(),
        int(nb_bytes / 3 / params.get_width())
    )
    if h <= 0:
        # no enough data for even one single line
        return None
    logger.info("Mode: RGB : Size: %dx%d", w, h)
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        img_bytes, GdkPixbuf.Colorspace.RGB,
        False,  # !has_alpha
        8,  # bits_per_sample
        w, h,
        w * 3,  # row_stride
    )
    logger.info("Pixbuf: Size: %dx%d", pixbuf.get_width(), pixbuf.get_height())
    return pixbuf


def raw2pillow(img_bytes, params):
    return PIL.Image.frombuffer(
        "RGB",
        (params.get_width(), int(len(img_bytes) / (params.get_width() * 3))),
        bytes(img_bytes), "raw", "RGB", 0, 1
    )
