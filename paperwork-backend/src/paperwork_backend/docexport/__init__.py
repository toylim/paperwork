"""
Doc and page exporting are designed as pipelines.
UI build the pipelines and run it.
"""

import openpaperwork_core


class AbstractExportPipe(object):
    """
    Pipes are used by the frontend/user to build an export pipeline.

    There are input pipes, taking either a doc URL (`doc_url`) or
    doc URL + page number (`page_url`) as input.
    There are output pipes, providing a file URL (`file_url`) as output.
    And there are processing pipes (usually taking Pillow images and text boxes
    as input (`pages`).

    Once the pipeline is defined, the frontend code can obtain promises
    from the pipes (`get_pipe()`), chain them together, and schedule them.
    """

    def __init__(self, name, input_types, output_type):
        """
        Common input/output types are:
        - pages: [(PIL.Image, line_boxes), ...]

        Common input-only types are:
        - doc_url
        - page_url: (doc_url, page_nb)

        Common output-only types are:
        - file_url
        """
        self.name = name
        self.input_types = input_types
        self.output_type = output_type
        self.can_change_quality = False
        self.can_change_page_format = False

        self.quality = 0.75
        self.page_format = (595.2755905511812, 841.8897637795276)  # A4

    def get_promise(self, input_data, result='final', target_file_url=None):
        """
        Returns a promise.

        Arguments:
        - result: either 'preview' (only one page) or 'final' (all pages)
        - target_file_url: Where the final pipe should write the file
          (None = temporary file)
        """
        assert()  # must be implemented by subclasses

    def set_quality(self, quality):
        assert(self.can_change_quality)

    def set_page_format(self, page_format):
        assert(self.can_change_page_format)

    def __str__(self):
        assert()  # must be implemented by subclasses


class AbstractExportPipePlugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.pipes = []

    def get_interfaces(self):
        return ['export_pipes']

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def export_get_pipe_by_name(self, name):
        for pipe in self.pipes:
            if pipe.name == name:
                return pipe

    def export_get_pipes_by_input(self, out: list, input_type):
        for pipe in self.pipes:
            if input_type in pipe.input_types:
                out.append(pipe)

    def export_get_pipes_by_doc_url(self, out: list, doc_url):
        for pipe in self.pipes:
            if hasattr(pipe, 'can_export_doc'):
                if pipe.can_export_doc(doc_url):
                    out.append(pipe)

    def export_get_pipes_by_page(self, out: list, doc_url, page_nb):
        for pipe in self.pipes:
            if hasattr(pipe, 'can_export_page'):
                if pipe.can_export_doc(doc_url, page_nb):
                    out.append(pipe)


class AbstractSimpleTransformExportPipe(AbstractExportPipe):
    def __init__(self, core, name):
        super().__init__(
            name=name,
            input_types=['pages'],
            output_type='pages'
        )
        self.core = core

    def transform(self, img):
        # sub-classes must implement it
        assert()

    def get_promise(self, result='final', target_file_url=None):
        def do(pages):
            if result != 'final':
                pages = [pages[0]]

            return [
                (self.transform(img), boxes)
                for (img, boxes) in pages
            ]

        return openpaperwork_core.promise.ThreadedPromise(self.core, func=do)
