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
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>

import logging
import os
import unicodedata


LOGGER = logging.getLogger(__name__)


def strip_accents(string):
    """
    Strip all the accents from the string
    """
    return u''.join(
        (
            character for character in unicodedata.normalize('NFD', string)
            if unicodedata.category(character) != 'Mn'
        )
    )


def rm_rf(path):
    """
    Act as 'rm -rf' in the shell
    """
    if os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                LOGGER.info("Deleting file %s" % filepath)
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                if os.path.islink(dirpath):
                    LOGGER.info("Deleting link %s" % dirpath)
                    os.unlink(dirpath)
                else:
                    LOGGER.info("Deleting dir %s" % dirpath)
                    os.rmdir(dirpath)
        LOGGER.info("Deleting dir %s", path)
        os.rmdir(path)
