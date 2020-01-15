#!/usr/bin/env python3
import sys

import setuptools


setuptools.setup(
    name="plugin-grapher",
    version="1.0",
    description="Generate graphic representing the plugins",
    url=(
        "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/"
        "plugin-grapher"
    ),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@openpaper.work",
    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'plugin-grapher = plugin_grapher.main:main',
        ],
    },
    zip_safe=True,
    install_requires=[
        "openpaperwork-core",
    ]
)
