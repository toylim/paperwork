import PIL.ImageDraw

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['pillow_util']

    def pillow_add_border(self, img, color="#a6a5a4", width=1):
        """
        Add a border of the specified color and width around a PIL image
        """
        img_draw = PIL.ImageDraw.Draw(img)
        for line in range(0, width):
            img_draw.rectangle(
                [
                    (line, line),
                    (
                        img.size[0] - 1 - line,
                        img.size[1] - 1 - line
                    )
                ],
                outline=color
            )
        return img
