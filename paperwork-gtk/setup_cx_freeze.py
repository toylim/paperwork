#!/usr/bin/env python3

import codecs
import glob
import os
import setuptools
import sys
import cx_Freeze


LOCALES = [
    "de",
    "fr",
    "uk",
]

ICON_SIZES = [
    16,
    22,
    24,
    30,
    32,
    36,
    42,
    48,
    50,
    64,
    72,
    96,
    100,
    128,
    150,
    160,
    192,
    256,
    512,
]

DOC_PATHS = [
    "doc/hacking.pdf",
    "doc/intro_fr.pdf",
    "doc/intro.pdf",
    "doc/translating.pdf",
    "doc/usage.pdf",
]


try:
    with codecs.open("src/paperwork/_version.py", "r", encoding="utf-8") \
            as file_descriptor:
        version = file_descriptor.readlines()[1].strip()
        version = version.split(" ")[2][1:-1]
    print("Paperwork version: {}".format(version))
    if "-" in version:
        version = version.split("-")[0]
except FileNotFoundError:
    print("ERROR: _version.py file is missing")
    print("ERROR: Please run 'make version' first")
    sys.exit(1)


packages = setuptools.find_packages('src') + [
    'paperwork.frontend.doc',
]
package_dir = {
    '': 'src',
    'paperwork.frontend.doc': 'doc',
}
package_data = {
    'paperwork.frontend': [
        'data/paperwork.svg',
        'data/paperwork_halo.svg',
    ],
    'paperwork.frontend.data': ['data/work.openpaper.Paperwork.appdata.xml'],
    'paperwork.frontend.doc': DOC_PATHS,
}

# include icons
packages.append("paperwork.frontend.data")
package_dir['paperwork.frontend.data'] = 'data'
for size in ICON_SIZES:
    icon_path = os.path.join("data", 'paperwork_{}.png'.format(size))
    package_data['paperwork.frontend.data'].append(icon_path)

# include locales
for locale in LOCALES:
    mo_dir = os.path.join("locale", locale, "LC_MESSAGES")
    mo = os.path.join(mo_dir, "paperwork.mo")
    pkg = "paperwork.frontend.locale.{}.LC_MESSAGES".format(locale)
    packages.append(pkg)
    package_dir[pkg] = mo_dir
    package_data[pkg] = [mo]


common_include_files = []

required_dll_search_paths = os.getenv("PATH", os.defpath).split(os.pathsep)
required_dlls = [
    'libatk-1.0-0.dll',
    'libepoxy-0.dll',
    'libgdk-3-0.dll',
    'libgdk_pixbuf-2.0-0.dll',
    'libgtk-3-0.dll',
    'libnotify-4.dll',
    'libpango-1.0-0.dll',
    'libpangocairo-1.0-0.dll',
    'libpangoft2-1.0-0.dll',
    'libpangowin32-1.0-0.dll',
    'libpoppler-*.dll',
    'libpoppler-glib-8.dll',
    'librsvg-2-2.dll',
    'libxml2-2.dll',

    'libinsane.dll',
    'libinsane_gobject.dll',
]

for dll in required_dlls:
    dll_path = None
    for p_dir in required_dll_search_paths:
        p_glob = os.path.join(p_dir, dll)
        for p in p_glob:
            if os.path.isfile(p):
                dll_path = p
                break
        if dll_path is not None:
            break
    if dll_path is None:
        raise Exception(
            "Unable to locate {} in {}".format(
                dll, required_dll_search_paths
            )
        )
    common_include_files.append((dll_path, dll))

# We need the .typelib files at runtime.
# The related .gir files are in $PREFIX/share/gir-1.0/$NS.gir,
# but those can be omitted at runtime.

required_gi_namespaces = [
    "Atk-1.0",
    "cairo-1.0",
    "Gdk-3.0",
    "GdkPixbuf-2.0",
    "Gio-2.0",
    "GLib-2.0",
    "GModule-2.0",
    "GObject-2.0",
    "Gtk-3.0",
    "Notify-0.7",
    "Pango-1.0",
    "PangoCairo-1.0",
    "Poppler-0.18",

    "Libinsane-1.0",
]

for ns in required_gi_namespaces:
    subpath = "lib/girepository-1.0/{}.typelib".format(ns)
    fullpath = os.path.join(sys.prefix, subpath)
    assert os.path.isfile(fullpath), (
        "Required file {} is missing" .format(
            fullpath,
        ))
    common_include_files.append((fullpath, subpath))

common_packages = [
    # XXX(Jflesch): known bug in cx_freeze
    'appdirs',
    'packaging',
    'pkg_resources',

    "six",
    "gi",   # always seems to be needed
    "cairo",   # Only needed (for foreign structs) if no "import cairo"s

    # XXX(Jflesch): bug ?
    "pyocr",
    "pyocr.libtesseract",
]


cx_Freeze.setup(
    name="paperwork",
    version=version,
    description=(
        "Using scanner and OCR to grep dead trees the easy way"
    ),
    long_description="""Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to
just scan a new document and forget about it until the day you need it
again.
Let the machine do most of the work.

Main features are:
- Scan
- Automatic orientation detection
- OCR
- Indexing
- Document labels
- Automatic guessing of the labels to apply on new documents
- Search
- Keyword suggestions
- Quick edit of scans
- PDF support
    """,
    keywords="scanner ocr gui",
    url="https://gitlab.gnome.org/World/OpenPaperwork/paperwork",
    download_url=("https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/"
                  "archive/{}/paperwork-{}.tar.gz".format(version, version)),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: X11 Applications :: GTK",
        "Environment :: X11 Applications :: Gnome",
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
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    entry_points={
        'gui_scripts': [
            'paperwork = paperwork.paperwork:main',
        ]
    },
    zip_safe=True,
    install_requires=[
        "python-dateutil",
        "python-Levenshtein",
        "Pillow",
        "pycountry",
        "pyocr >= 0.3.0",
        "pypillowfight",
        "pyxdg >= 0.25",
        "termcolor",  # used by paperwork-chkdeps
        "paperwork-backend>={}".format(version),
    ],
    executables=[
        cx_Freeze.Executable(
            script="src/launcher.py",
            targetName="paperwork.exe",
            base=("Console" if os.name != "nt" else "Win32GUI"),
        ),
    ],
    options={
        "build_exe": {
            'include_files': common_include_files,
            'silent': True,
            'packages': common_packages,
            "excludes": ["tkinter", "tk", "tcl"],
        },
    },
)
