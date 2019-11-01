import gettext

import openpaperwork_core

from . import AbstractImgEditor


_ = gettext.gettext


class CropImgEditor(AbstractImgEditor):
    def __init__(self, frame):
        self.frame = frame

    def transform(self, img, preview=False):
        if preview:
            # we do not crop the preview. The UI displays a frame on top
            # of it showing where the cropping will happen.
            return img
        ((tl_x, tl_y), (br_x, br_y)) = self.frame
        img = img.crop((tl_x, tl_y, br_x, br_y))
        return img


class Plugin(openpaperwork_core.PluginBase):
    NAME = 'cropping'

    def get_interfaces(self):
        return ['img_editor']

    def get_deps(self):
        return {}

    def img_editor_get_names(self, out: list):
        out.append(self.NAME)

    def img_editor_get(self, name, *args, **kwargs):
        if name != self.NAME:
            return None
        frame = kwargs.pop('frame')
        return CropImgEditor(frame)

    def img_editor_set(self, inout: list, name, *args, **kwargs):
        if name != self.NAME:
            return None
        frame = kwargs.pop('frame')
        c = CropImgEditor(frame)
        try:
            # Check if we already have a CropImgEditor in the list.
            # If so, update it instead of adding another one
            index = inout.index(c)
            inout[index].frame = frame
        except ValueError:
            inout.append(c)

    def img_editor_unset(self, inout: list, name):
        if name != self.NAME:
            return None
        c = CropImgEditor(((0, 0), (0, 0)))  # frame doesn't matter here
        while c in inout:
            inout.remove(c)
