## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) carefully before submitting any
merge request.

In this document, it is assumed you are already familiar with the basics of
Git.


## Paperwork in a Virtualenv

This is the recommended approach for development. If you intend to work on
Paperwork (or just try it), this is probably the most convenient way to
install safely a development version of Paperwork.

Virtualenv allows to run Paperwork in a specific environment, with the latest
versions of most of its dependencies. It also make it easier to remove it (you
just have to delete the directory containing the virtualenv). However the user
that did the installation will be the only one able to run Paperwork. No
shortcut will be installed in the menus of your window manager. Paperwork
won't be available directly on your PATH.

Paperwork depends on various libraries. Development should be done against the
latest versions of the OpenPaper.work's librairies (Libinsane, Libpillowfight,
PyOCR, etc). To make things simpler, Paperwork repository includes a script
to create and load a Python virtualenv (`source ./activate_test_env.sh`).
It will automatically get OpenPaper.work's librairies fresh from Git and
install them in this virtualenv.
Then the command `make install` will install Paperwork components using Python
setuptools. Python setuptools will automatically fetch and install pure-Python
dependencies. Finally, `paperwork-cli chkdeps` and `paperwork-gtk chkdeps`
will take care of installing the remaining dependencies system-wide using the
package manager of your Linux distribution (APT, Dnf, Pacman, etc).


### Requirements

You will have to install
[python3-virtualenv](https://pypi.python.org/pypi/virtualenv):

```sh
sudo apt install python3-virtualenv virtualenv python3-dev
```

[Libinsane](https://gitlab.gnome.org/World/OpenPaperwork/libinsane/-/blob/master/README.markdown)
will also be built. This build requires various dependencies:

```sh
sudo apt install \
        gettext \
        make \
        meson \
        build-essential \
        libsane-dev \
        libgirepository1.0-dev gobject-introspection \
        python3-gi \
        valac \
        gtk-doc-tools
```


### Setting up a virtualenv


```sh
mkdir -p ~/git
cd ~/git

git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork

# - 'develop' is the branch where any new features, bug fixes, etc should go by
#   default.
# - 'testing' is only for bug fixes, translations and documentations during
#   the testing phase *only*
# - 'master' is the latest stable version of Paperwork + some bug fixes (only
#   the project maintainer add commits in this branch).
git checkout develop

# Will create the Python virtualenv if it doesn't exist.
# It will compile Libinsane and some other librairies. It will then set the
# correct environment variables to use them without installing them
# system-wide.
source ./activate_test_env.sh

# you're now in the virtualenv

# 'make install' will install Paperwork in the virtualenv
make install

# takes care of the dependencies that cannot be installed in the virtualenv
# (Gtk, Tesseract, etc)
paperwork-cli chkdeps
paperwork-gtk chkdeps
```


### Running Paperwork from the virtualenv

```sh
cd ~/git/paperwork

source ./activate_test_env.sh
# you're now in a virtualenv

# Running your version of Paperwork:
paperwork-gtk
```


### Updating

```sh
cd ~/git/paperwork

git pull

make clean
git submodule update --recursive --remote

source ./activate_test_env.sh
# you're now in a virtualenv

make install
```


Enjoy :-)
