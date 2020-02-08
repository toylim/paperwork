import gettext

import openpaperwork_core

import PIL
import PIL.Image


from . import AbstractImgEditor


_ = gettext.gettext


class RotationImgEditor(AbstractImgEditor):
    def __init__(self, angle):
        self.angle = angle % 360

    def transform(self, img, preview=False):
        # Pillow operates counter-clockwise, we operate clockwise.
        if self.angle == 0:
            return img
        angle = {
            90: PIL.Image.ROTATE_90,
            180: PIL.Image.ROTATE_180,
            270: PIL.Image.ROTATE_270,
        }[self.angle]
        return img.transpose(angle)

    def transform_frame(self, img_size, frame):
        frame = (
            self.transform_point(img_size, frame[0]),
            self.transform_point(img_size, frame[1]),
        )
        return (
            (
                min(frame[0][0], frame[1][0]),
                min(frame[0][1], frame[1][1]),
            ),
            (
                max(frame[0][0], frame[1][0]),
                max(frame[0][1], frame[1][1]),
            ),
        )

    def _transform_pt(self, img_size, pt, angle):
        r = {
            0: pt,
            90: (img_size[1] - pt[1], pt[0]),
            180: (img_size[0] - pt[0], img_size[1] - pt[1]),
            270: (pt[1], img_size[0] - pt[0]),
        }[angle]
        return r

    def transform_point(self, img_size, pt):
        return self._transform_pt(img_size, pt, self.angle)

    def untransform_point(self, img_size, pt):
        # we are given the image size before we apply our transformation
        # but here we want to go the other way around
        img_size = {
            0: img_size,
            90: (img_size[1], img_size[0]),
            180: img_size,
            270: (img_size[1], img_size[0]),
        }[self.angle]
        angle = ((-1 * self.angle) % 360)
        return self._transform_pt(img_size, pt, angle)


class Plugin(openpaperwork_core.PluginBase):
    NAME = 'rotation'

    def get_interfaces(self):
        return ['img_editor']

    def img_editor_get_names(self, out: list):
        out.append(self.NAME)

    def img_editor_get(self, name, *args, **kwargs):
        if name != self.NAME:
            return None
        angle = kwargs.pop('angle')
        return RotationImgEditor(angle)

    def img_editor_set(self, inout: list, name, *args, **kwargs):
        if name != self.NAME:
            return None
        angle = kwargs.pop('angle')
        c = RotationImgEditor(angle)
        try:
            # Check if we already have a RotationImgEditor in the list.
            # If so, update it instead of adding another one
            index = inout.index(c)
            inout[index].angle += angle
        except ValueError:
            inout.append(c)

    def img_editor_unset(self, inout: list, name):
        if name != self.NAME:
            return None
        c = RotationImgEditor(0)
        while c in inout:
            inout.remove(c)