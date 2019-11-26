import PIL
import PIL.Image

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSIONS = [
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "tiff",
    ]

    def get_interfaces(self):
        return ['pillow']

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio',]),
            ]
        }

    def url_to_pillow(self, file_url):
        if file_url.split(".")[-1] not in self.FILE_EXTENSIONS:
            return None
        with self.core.call_success("fs_open", file_url, mode='rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            return img

    def pillow_to_url(self, img, file_url, format='JPEG', quality=0.75):
        with self.core.call_success("fs_open", file_url, mode='wb') as fd:
            return img.save(fd, format=format, quality=int(quality * 100))
