#!/usr/bin/env python3

import sys

from setuptools import setup, find_packages


quiet = '--quiet' in sys.argv or '-q' in sys.argv

try:
    with open("src/openpaperwork_core/_version.py", "r") as file_descriptor:
        version = file_descriptor.read().strip()
        version = version.split(" ")[2][1:-1]
    if not quiet:
        print("OpenPaperwork-core version: {}".format(version))
    if "-" in version:
        version = version.split("-")[0]
except FileNotFoundError:
    print("ERROR: _version.py file is missing")
    print("ERROR: Please run 'make version' first")
    sys.exit(1)


setup(
    name="openpaperwork-core",
    version=version,
    description=(
        "OpenPaperwork's core"
    ),
    long_description="""Paperwork is a GUI to make papers searchable.

This is the core part of Paperwork. It manages plugins.

There is no GUI here. The GUI is
<https://gitlab.gnome.org/World/OpenPaperwork/paperwork#readme>.
    """,
    url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/"
        "openpaperwork-core"
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
    include_package_data=True,
    package_dir={'': 'src'},
    zip_safe=True,
    install_requires=[
        "distro",  # chkdeps
    ]
)
