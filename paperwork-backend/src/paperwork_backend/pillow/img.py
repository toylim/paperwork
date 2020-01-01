import logging
import time

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


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
        return [
            'page_img_size',
            'pillow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            }
        ]

    def _check_is_img(self, file_url):
        return file_url.split(".")[-1] in self.FILE_EXTENSIONS

    def url_to_img_size(self, file_url):
        if not self._check_is_img(file_url):
            return None
        start = time.time()
        with self.core.call_success("fs_open", file_url, mode='rb') as fd:
            img = PIL.Image.open(fd)
            size = img.size
        stop = time.time()
        LOGGER.info(
            "Took %dms to get size of %s: %s",
            (stop - start) * 1000, file_url, size
        )
        return img

    def url_to_pillow(self, file_url):
        if not self._check_is_img(file_url):
            return None
        start = time.time()
        with self.core.call_success("fs_open", file_url, mode='rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
        stop = time.time()
        LOGGER.info(
            "Took %dms to render %s as a Pillow image",
            (stop - start) * 1000, file_url
        )
        return img

    def url_to_pillow_promise(self, file_url):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, img, file_url, format='JPEG', quality=0.75):
        with self.core.call_success("fs_open", file_url, mode='wb') as fd:
            return img.save(fd, format=format, quality=int(quality * 100))
