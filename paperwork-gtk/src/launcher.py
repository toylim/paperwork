#!/usr/bin/env python3
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

# just here to run a non-installed version

import os
import multiprocessing
import sys


def set_meipass():
    # If sys.frozen, then Pyocr needs MEIPASS to be set
    # *before* importing it
    if getattr(sys, '_MEIPASS', False):
        # Pyinstaller case
        return
    # Cx_Freeze case
    sys._MEIPASS = os.path.dirname(os.path.realpath(sys.executable))


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        set_meipass()
        multiprocessing.freeze_support()
    else:
        sys.path += ['src']
        data_base_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), ".."
        )
        os.chdir(data_base_path)

    from paperwork.paperwork import main
    main()
