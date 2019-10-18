import gettext
import logging

import pillowfight


from . import (
    AbstractExportPipePlugin,
    AbstractSimpleTransformExportPipe
)


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class UnpaperExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "unpaper")

    def transform(self, img):
        # Unpaper algorithms in Unpaper's order
        img = pillowfight.unpaper_blackfilter(img)
        img = pillowfight.unpaper_noisefilter(img)
        img = pillowfight.unpaper_blurfilter(img)
        img = pillowfight.unpaper_masks(img)
        img = pillowfight.unpaper_grayfilter(img)
        img = pillowfight.unpaper_border(img)
        return img

    def __str__(self):
        _("Soft simplification")


class SwtExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core, swt_output_type):
        super().__init__(
            core,
            "swt_soft"
            if swt_output_type == pillowfight.SWT_OUTPUT_ORIGINAL_BOXES
            else "swt_hard"
        )
        self.output_type = swt_output_type

    def transform(self, pil_img):
        pil_img = pil_img.convert("L")
        return pillowfight.swt(pil_img, output_type=self.output_type)

    def __str__(self):
        if self.output_type == pillowfight.SWT_OUTPUT_ORIGINAL_BOXES:
            _("Hard")
        else:
            _("Extreme")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            UnpaperExportPipe(core),
            SwtExportPipe(core, pillowfight.SWT_OUTPUT_ORIGINAL_BOXES),
            SwtExportPipe(core, pillowfight.SWT_OUTPUT_BW_TEXT),
        ]

    def get_deps(self):
        return {
            "interfaces": [
                ('mainloop', ['openpaperwork_core.mainloop_asyncio']),
            ]
        }
