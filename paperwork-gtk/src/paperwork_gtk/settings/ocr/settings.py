import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -500

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

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings.ocr",
            "settings.glade"
        )

        label = widget_tree.get_object("ocr_langs_label")
        self._update_langs(label)

        button = widget_tree.get_object("ocr_langs")

        popover = self.core.call_success("get_ocr_lang_selector")
        if popover is not None:
            popover.connect("closed", self._on_ocr_langs_changed, label)
            button.set_popover(popover)

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree,
            _("Optical Character Recognition"),
            [button]
        )

    def _update_langs(self, label):
        langs = self.core.call_success("ocr_get_active_langs")
        langs = [
            self.core.call_success("i18n_lang_iso639_3_to_full", lang)
            for lang in langs
        ]
        langs = ", ".join(langs)
        if langs == "":
            langs = _("None")
        LOGGER.info("OCR languages: %s", langs)
        label.set_text(langs)

    def _on_ocr_langs_changed(self, _, label):
        self._update_langs(label)
