#!/usr/bin/env python3
import sys

import setuptools


quiet = '--quiet' in sys.argv or '-q' in sys.argv


try:
    with open("src/paperwork_shell/_version.py", "r") as file_descriptor:
        version = file_descriptor.read().strip()
        version = version.split(" ")[2][1:-1]
    if not quiet:
        print("Paperwork-shell version: {}".format(version))
    if "-" in version:
        version = version.split("-")[0]
except FileNotFoundError:
    print("ERROR: _version.py file is missing")
    print("ERROR: Please run 'make version' first")
    sys.exit(1)


setuptools.setup(
    name="paperwork-shell",
    version=version,
    description="Paperwork's shell interface",
    long_description="""Paperwork is a GUI to make papers searchable.

- paperwork-cli : a interactive shell frontend for Paperwork.

- paperwork-json : a non-interactive shell frontend for Paperwork that always
  return JSON results.
""",
    keywords="documents",
    url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/"
        "paperwork-shell"
    ),
    download_url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-"
        "/archive/{}/paperwork-{}.tar.gz".format(version, version)
    ),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Graphics :: Capture :: Scanners",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Indexing",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@openpaper.work",
    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'paperwork-cli = paperwork_shell.main:cli_main',
            'paperwork-json = paperwork_shell.main:json_main',
        ],
    },
    zip_safe=True,
    install_requires=[
        "fabulous",
        "openpaperwork-core",
        "paperwork-backend",
    ]
)

if quiet:
    sys.exit(0)

print("============================================================")
print("============================================================")
print("||                       IMPORTANT                        ||")
print("||          Please run 'paperwork-cli chkdeps'            ||")
print("||            to find any missing dependency              ||")
print("============================================================")
print("============================================================")
