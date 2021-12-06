import os
import tempfile

try:
    import fabulous.image
    # XXX(Jflesch): crappy workaround for an unmaintained library ...
    fabulous.image.basestring = str
    FABULOUS_AVAILABLE = True
except (ValueError, ImportError):
    FABULOUS_AVAILABLE = False

import openpaperwork_core


class FabulousRenderer(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core
        self.parent = None

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        w_split = int(terminal_size[0] / 3)

        parent = []
        if self.parent is not None:
            parent = self.parent.get_preview_output(
                doc_id, doc_url,
                (terminal_size[0] - w_split - 2, terminal_size[1]),
                page_idx
            )

        thumbnail = self.core.call_success(
            "thumbnail_get_page", doc_url, page_idx
        )
        if thumbnail is None:
            thumbnail = []
        else:
            thumbnail = self.plugin.img_render(thumbnail, w_split)

        if len(parent) < len(thumbnail):
            parent.extend([""] * (len(thumbnail) - len(parent)))
        elif len(parent) > len(thumbnail):
            parent = parent[:len(thumbnail)]

        out = [
            (i + " " + t)
            for (i, t) in zip(thumbnail, parent)
        ]

        return out

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_doc_output(
                doc_id, doc_url, terminal_size
            )
        return out

    def get_page_output(
                self, doc_id, doc_url, page_nb, terminal_size=(80, 25)
            ):
        parent_out = []
        if self.parent is not None:
            parent_out = self.parent.get_page_output(
                doc_id, doc_url, page_nb, terminal_size
            )

        img_url = self.core.call_success("page_get_img_url", doc_url, page_nb)
        img = self.core.call_success("url_to_pillow", img_url)
        img = self.plugin.img_render(
            img, terminal_width=(terminal_size[0] - 1)
        )
        return [img_url] + list(img) + [""] + parent_out

    def get_doc_infos(self, doc_id, doc_url):
        out = {}
        if self.parent is not None:
            out = self.parent.get_doc_infos(doc_id, doc_url)
        return out

    def get_page_infos(self, doc_id, doc_url, page_nb):
        out = {}
        if self.parent is not None:
            out = self.parent.get_page_infos(doc_id, doc_url, page_nb)
        out['image'] = self.core.call_success(
            "page_get_img_url", doc_url, page_nb
        )
        return out


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def get_interfaces(self):
        return [
            'doc_renderer',
            'img_renderer',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'thumbnail',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
        ]

    def doc_renderer_get(self, out):
        if not FABULOUS_AVAILABLE:
            return
        r = FabulousRenderer(self)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)

    def img_render(self, img, terminal_width=80):
        if not FABULOUS_AVAILABLE:
            return
        with tempfile.NamedTemporaryFile(
                    prefix='paperwork-shell', suffix='.jpeg',
                    delete=False
                ) as fd:
            img.save(fd, format="JPEG")
            img_file = fd.name
        try:
            img = fabulous.image.Image(img_file, width=terminal_width)
            img = img.reduce(img.convert())
        finally:
            os.unlink(img_file)
        return list(img)
