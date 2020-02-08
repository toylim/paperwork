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
            'gtk_settings_ocr_langs',
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

    def get_ocr_lang_selector(self):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.settings.ocr", "selector_popover.glade"
        )

        active_langs = set(self.core.call_success("ocr_get_active_langs"))
        LOGGER.info("Looking for available OCR languages ...")
        all_langs = self.core.call_success("ocr_get_available_langs")
        LOGGER.info("Found %d languages. Translating ...".format(
            len(all_langs)
        ))
        all_langs = [
            (
                lang,
                self.core.call_success(
                    "i18n_lang_iso639_3_to_full", lang
                )
            )
            for lang in all_langs
        ]
        all_langs.sort(key=lambda l: l[1])

        LOGGER.info("OCR languages: %s", all_langs)
        LOGGER.info("Active OCR languages: %s", active_langs)

        box_parent = widget_tree.get_object("ocr_selector_box")

        for lang in all_langs:
            w_tree = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.settings.ocr", "selector_popover_box.glade"
            )
            check = w_tree.get_object("ocr_selector_box")
            check.set_label(lang[1])
            check.set_active(lang[0] in active_langs)
            check.connect('toggled', self._on_toggle, lang[0])
            box_parent.pack_start(check, expand=False, fill=True, padding=0)
        LOGGER.info("OCR selector ready")
        return widget_tree.get_object("ocr_selector")

    def _on_toggle(self, checkbox, lang):
        active_langs = self.core.call_success("ocr_get_active_langs")
        lang_enabled = lang in active_langs
        LOGGER.info("Language toggled: {} ({} -> {})".format(
            lang, lang_enabled, not lang_enabled
        ))
        if lang_enabled:
            active_langs.remove(lang)
        else:
            active_langs.append(lang)
        self.core.call_all("ocr_set_active_langs", active_langs)