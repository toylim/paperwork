import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -500

    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return [
            'gtk_settings',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'i18n_lang',
                'defaults': ['paperwork_backend.i18n.pycountry'],
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)

    def complete_settings_dialog(self, settings_box):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "ocr.glade"
        )

        langs = self.core.call_success("ocr_get_langs")
        langs = [
            self.core.call_success("i18n_lang_iso639_3_to_full", lang)
            for lang in langs
        ]
        langs = ", ".join(langs)
        LOGGER.info("OCR languages: %s", langs)
        widget_tree.get_object("ocr_langs_label").set_text(str(langs))

        self.core.call_success(
            "add_setting_to_dialog", settings_box,
            _("Optical Character Recognition"),
            [widget_tree.get_object("ocr_langs_box")]
        )
