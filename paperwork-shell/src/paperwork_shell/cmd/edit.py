#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2019  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
import gettext
import logging
import shutil
import sys

import openpaperwork_core

import paperwork_backend.pageedit

from . import util


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class NullUI(paperwork_backend.pageedit.AbstractPageEditorUI):
    pass


class CliUI(paperwork_backend.pageedit.AbstractPageEditorUI):
    def __init__(self, core):
        super().__init__()
        self.core = core

    def show_preview(self, img):
        terminal_width = shutil.get_terminal_size()[0] - 1
        img = self.core.call_success(
            "img_render", img, terminal_width=terminal_width
        )
        if img is None:
            return
        for line in img:
            print(line)
        print()


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.interactive = False

    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            # optional dependency
            # {
            #     "interface": "img_renderer",
            #     "defaults": ["paperwork_shell.display.docrendering.img"],
            # },
            {
                "interface": "page_editor",
                "defaults": ["paperwork_backend.pageedit.pageeditor"],
            },
        ]

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        # just so we can get the modifier list
        editor = self.core.call_success("page_editor_get", None, 0, NullUI())
        modifiers = editor.get_modifiers()

        modifiers = [
            modifier['id']
            for modifier in modifiers
            if not modifier['need_frame']
        ]

        edit_parser = parser.add_parser('edit', help=_("Edit page"))
        edit_parser.add_argument(
            '--modifiers', '-m', type=str, required=True,
            help=_(
                "List of image modifiers (comma separated, possible values:"
                " {})"
            ).format(modifiers)
        )
        # we need page number(s), but for consistency with other commnads,
        # we require this argument as an option like '--opt' instead of
        # a positional argument.
        edit_parser.add_argument('--pages', '-p', type=str, required=True)
        edit_parser.add_argument('doc_id')

    def cmd_run(self, args):
        if args.command != 'edit':
            return None
        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        pages = util.parse_page_list(args)
        modifiers = args.modifiers.split(",")
        out = []

        for page_idx in pages:
            out.append((doc_id, page_idx))
            if self.interactive:
                print(
                    _("Modifying document {} page {} ...").format(
                        doc_id, page_idx
                    )
                )
                print(_("Original:"))
                ui = CliUI(self.core)
            else:
                ui = NullUI()

            page_editor = self.core.call_success(
                "page_editor_get", doc_url, page_idx, ui
            )

            promise = openpaperwork_core.promise.Promise(self.core)
            for modifier in modifiers:
                if self.interactive:
                    promise = promise.then(print, "{}:".format(modifier))
                promise = promise.then(
                    page_editor.on_modifier_selected(modifier)
                )

            if promise is not None:
                if self.interactive:
                    promise = promise.then(
                        sys.stdout.write,
                        _("Generating in high quality and saving ...") + " "
                    )
                    promise = promise.then(
                        lambda *args, **kwargs: sys.stdout.flush()
                    )

                promise = promise.then(page_editor.on_save())

                if self.interactive:
                    promise = promise.then(print, "Done")

                def on_err(exc):
                    LOGGER.error(
                        "Edition of %s p%d failed",
                        doc_id, page_idx,
                        exc_info=exc
                    )
                    page_editor.on_cancel()
                    raise exc

                promise.catch(on_err)

                promise.schedule()

                self.core.call_all("mainloop_quit_graceful")
                self.core.call_one("mainloop")

        if self.interactive:
            sys.stdout.write(_("Committing ...") + " ")
            sys.stdout.flush()

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.upd_obj(doc_id)
        for transaction in transactions:
            transaction.commit()

        if self.interactive:
            print(_("Done"))
            print(_("All done !"))

        return out
