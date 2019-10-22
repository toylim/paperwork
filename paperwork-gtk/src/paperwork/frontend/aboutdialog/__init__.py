#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
"""
Contains the code relative to the about dialog (the one you get when you click
on Help->About)
"""

import gettext
import os

from gi.repository import GdkPixbuf

from ... import _version

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util import preload_file


_ = gettext.gettext


class AboutDialog(object):

    """
    Dialog that appears when you click Help->About.

    By default, this dialog won't be visible. You have to call
    AboutDialog.show().
    """

    def __init__(self, main_window):
        logo_path = preload_file("paperwork.svg")
        self.__widget_tree = load_uifile(
            os.path.join("aboutdialog", "aboutdialog.glade"))

        self.__dialog = self.__widget_tree.get_object("aboutdialog")
        assert(self.__dialog)
        self.__dialog.set_transient_for(main_window)

        self.__dialog.set_version(_version.version)
        self.__dialog.set_authors(_version.authors_code.split("\n"))
        self.__dialog.set_documenters(
            _version.authors_documentation.split("\n")
        )
        self.__dialog.set_translator_credits(_version.authors_translators)
        self.__dialog.add_credit_section(
            _("UI design"), _version.authors_ui.split("\n")
        )
        self.__dialog.add_credit_section(
            _("Patrons"), _version.patrons.split("\n")
        )

        if logo_path and os.access(logo_path, os.F_OK):
            logo = GdkPixbuf.Pixbuf.new_from_file(logo_path)
            self.__dialog.set_logo(logo)
        self.__dialog.connect("response", lambda x, y: x.destroy())

    def show(self):
        """
        Make the about dialog appears
        """
        self.__dialog.set_visible(True)
