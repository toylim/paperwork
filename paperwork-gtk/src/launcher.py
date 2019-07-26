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


if __name__ == "__main__":
    if "python" not in sys.executable or '__file__' not in globals():
        data_base_path = os.path.dirname(os.path.realpath(sys.executable))
    else:
        data_base_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), ".."
        )
    os.chdir(data_base_path)

    from paperwork.paperwork import main
    main()
