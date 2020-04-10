#!/usr/bin/env python3

import sys

from setuptools import setup, find_packages


quiet = '--quiet' in sys.argv or '-q' in sys.argv

try:
    with open("src/openpaperwork_gtk/_version.py", "r") as file_descriptor:
        version = file_descriptor.read().strip()
        version = version.split(" ")[2][1:-1]
    if not quiet:
        print("OpenPaperwork-gtk version: {}".format(version))
    if "-" in version:
        version = version.split("-")[0]
except FileNotFoundError:
    print("ERROR: _version.py file is missing")
    print("ERROR: Please run 'make version' first")
    sys.exit(1)


setup(
    name="openpaperwork-gtk",
    version=version,
    description=(
        "OpenPaperwork GTK plugins"
    ),
    long_description="""Paperwork is a GUI to make papers searchable.

A bunch of plugins for Paperwork related to GLib and GTK.
    """,
    url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/"
        "openpaperwork-gtk"
    ),
    download_url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-"
        "/archive/{}/paperwork-{}.tar.gz".format(version, version)
    ),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@openpaper.work",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=True,
    install_requires=[]
)
