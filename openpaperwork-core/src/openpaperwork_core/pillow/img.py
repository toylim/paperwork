import logging

import PIL
import PIL.Image

from .. import (
    PluginBase,
    promise
)


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    FILE_EXTENSIONS = [
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "tif",
        "tiff",
    ]

    def get_interfaces(self):
        return [
            'page_img_size',
            'pillow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python']
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def _check_is_img(self, file_url):
        return file_url.rsplit(".", 1)[-1].lower() in self.FILE_EXTENSIONS

    def url_to_img_size(self, file_url):
        if not self._check_is_img(file_url):
            return None

        task = "url_to_img_size({})".format(file_url)
        self.core.call_all("on_perfcheck_start", task)

        with self.core.call_success("fs_open", file_url, mode='rb') as fd:
            img = PIL.Image.open(fd)
            size = img.size

        self.core.call_all("on_perfcheck_stop", task, size=size)
        return size

    def url_to_img_size_promise(self, file_url):
        if not self._check_is_img(file_url):
            return None

        return promise.ThreadedPromise(
            self.core, self.url_to_img_size, args=(file_url,)
        )

    def url_to_pillow(self, file_url):
        if not self._check_is_img(file_url):
            return None

        task = "url_to_pillow({})".format(file_url)
        self.core.call_all("on_perfcheck_start", task)

        with self.core.call_success("fs_open", file_url, mode='rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            self.core.call_all("on_objref_track", img)
            size = img.size

        self.core.call_all("on_perfcheck_stop", task, size=size)
        return img

    def url_to_pillow_promise(self, file_url):
        return promise.ThreadedPromise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, img, file_url, format='JPEG', quality=0.75):
        if format != 'PNG':
            img = img.convert("RGB")
        with self.core.call_success("fs_open", file_url, mode='wb') as fd:
            return img.save(fd, format=format, quality=int(quality * 100))
