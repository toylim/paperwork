import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from .. import PluginBase


class Plugin(PluginBase):
    ID_TO_MSG = {
        'too_big': "Image too big.\nImage not loaded.",
    }

    def get_interfaces(self):
        return ['pillow_util']

    def pillow_get_error(self, error_id):
        msg = self.ID_TO_MSG[error_id]
        longest_line = max(((len(line), line) for line in msg.split("\n")))
        longest_line = longest_line[1]

        font = PIL.ImageFont.load_default()
        size_func = getattr(
            font, 'getbbox',
            getattr(
                font, 'getsize',
                lambda txt: (400, 400)
            )
        )
        size = size_func(longest_line)
        size = (size[0], size[1] * (1 + (2 * msg.count("\n"))))

        img = PIL.Image.new("RGB", size, (255, 255, 255))
        draw = PIL.ImageDraw.Draw(img)
        draw.text((0, 0), msg, font=font, fill=(0, 0, 0))

        img = img.resize(
            tuple([s * 8 for s in size]),
            getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS
        )

        return img

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
