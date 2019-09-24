import os
import tempfile

import fabulous.image

import openpaperwork_core


# XXX(Jflesch): crappy workaround for an unmaintained library ...
fabulous.image.basestring = str


class FabulousRenderer(object):
    def __init__(self, core):
        self.core = core
        self.parent = None

    def get_preview_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_preview_output(
                doc_id, doc_url, terminal_size
            )
        # TODO
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

        img = self.core.call_success("page_get_img_url", doc_url, page_nb)
        img = self.core.call_success("url_to_pillow", img)

        with tempfile.NamedTemporaryFile(
                    prefix='paperwork-shell', suffix='.jpeg',
                    delete=False
                ) as fd:
            img.save(fd, format="JPEG")
            img_file = fd.name
        try:
            img = fabulous.image.Image(img_file, width=(terminal_size[0] - 1))
            img = img.reduce(img.convert())
        finally:
            os.unlink(img_file)

        return list(img) + [""] + parent_out

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
        return ['doc_renderer']

    def get_deps(self):
        return {
            'interfaces': [
                ("page_img", [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ]),
                ("pillow", [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]),
            ]
        }

    def doc_renderer_get(self, out):
        r = FabulousRenderer(self.core)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)
