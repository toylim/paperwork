try:
    import fabulous.color
    FABULOUS_AVAILABLE = True
except (ValueError, ImportError):
    FABULOUS_AVAILABLE = False

import openpaperwork_core

import rich.text


def color_labels(core, labels):
    labels = [
        (label, core.call_success("label_color_to_rgb", color))
        for (label, color) in labels
    ]
    labels = [
        (label, (
            int(color[0] * 0xFF),
            int(color[1] * 0xFF),
            int(color[2] * 0xFF)
        ))
        for (label, color) in labels
    ]

    for (label, bg_color) in labels:
        fg_color = core.call_success(
            "label_get_foreground_color",
            (
                bg_color[0] / 0xFF,
                bg_color[1] / 0xFF,
                bg_color[2] / 0xFF,
            )
        )
        fg_color = (fg_color[0] * 0xFF, fg_color[1] * 0xFF, fg_color[2] * 0xFF)
        l_label = len(label)
        label = fabulous.color.fg256(fg_color, label)
        label = fabulous.color.bg256(bg_color, label)
        yield (l_label, str(label))


class LabelsRenderer(object):
    def __init__(self, core):
        self.core = core
        self.parent = None

    def _get_labels(self, doc_url):
        labels = set()
        self.core.call_all("doc_get_labels_by_url", labels, doc_url)
        return labels

    def _rearrange_labels(self, labels, terminal_width):
        out = []
        line = ""
        for (len_label, label) in labels:
            if len(line) + len_label + 1 >= terminal_width:
                out.append(line)
                line = ""
            line += " " + label
        if len(line.strip()) > 0:
            out.append(line)
        return [line.strip() for line in out]

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        out = []
        if self.parent is not None:
            out = self.parent.get_preview_output(
                doc_id, doc_url, terminal_size, page_idx
            )
        if not FABULOUS_AVAILABLE:
            return out
        if page_idx != 0:
            return out

        labels = self._get_labels(doc_url)
        labels = color_labels(self.core, labels)
        labels = self._rearrange_labels(labels, terminal_size[0])
        return labels + out

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_doc_output(
                doc_id, doc_url, terminal_size
            )
        if not FABULOUS_AVAILABLE:
            return out

        labels = self._get_labels(doc_url)
        labels = color_labels(self.core, labels)
        labels = self._rearrange_labels(labels, terminal_size[0])
        return labels + out

    def get_page_output(
                self, doc_id, doc_url, page_nb, terminal_size=(80, 25)
            ):
        if self.parent is not None:
            return self.parent.get_page_output(
                doc_id, doc_url, page_nb, terminal_size
            )
        return []

    def get_doc_infos(self, doc_id, doc_url):
        out = {}
        if self.parent is not None:
            out = self.parent.get_doc_infos(doc_id, doc_url)
        out['labels'] = []
        for (label, color) in self._get_labels(doc_url):
            out['labels'].append(
                {
                    'label': label,
                    'color': color,
                }
            )
        return out

    def get_page_infos(self, doc_id, doc_url, page_nb):
        if self.parent is not None:
            return self.parent.get_page_infos(doc_id, doc_url, page_nb)
        return {}


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def get_interfaces(self):
        return ['doc_renderer']

    def get_deps(self):
        return [
            {
                'interface': 'page_boxes',
                'defaults': ['paperwork_backend.model.labels'],
            },
        ]

    def format_labels(self, labels, separator='\n'):
        if FABULOUS_AVAILABLE:
            labels = color_labels(self.core, labels)
            labels = [label for (l_label, label) in labels]
            labels = separator.join(labels)
            labels = rich.text.Text.from_ansi(labels)
        else:
            labels = [label for (label, color) in labels]
            labels = separator.join(labels)
        return labels

    def doc_renderer_get(self, out):
        r = LabelsRenderer(self.core)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)
