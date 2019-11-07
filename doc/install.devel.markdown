## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) carefully before submitting any
merge request.

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

Libinsane is scan library required by Paperwork. You need it in your
development environment. There are other dependencies that may be required.

To make things simpler, Paperwork repository includes a script
(`activate\_test\_env.sh`) to create a Python virtualenv including Libinsane
and any other possible dependencies. The Makefile (`make install`) can install
most of the dependencies and Paperwork components in one shot.
`paperwork-shell` can then take care of installing some dependencies that
can only be installed system-wide.


### Requirements

For Paperwork, you will have to install
[python3-virtualenv](https://pypi.python.org/pypi/virtualenv):

```sh
sudo apt install python3-virtualenv virtualenv python3-dev
```

You will also need to build Libinsane [from
sources](https://doc.openpaper.work/libinsane/latest/libinsane/install.html):

```sh
sudo apt install \
        make \
        meson \
        build-essential \
        libsane-dev \
        libgirepository1.0-dev gobject-introspection \
        python3-gi \
        valac
```


### Setting up a development environment


```sh
mkdir -p ~/git
cd ~/git

git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork
git checkout develop  # or 'master', 'release-xxx', 'wip-xxx', etc

# Will create the Python virtualenv if it doesn't exist.
# It will compile Libinsane and set the correct environment variables to use it
# without installing it
source ./activate_test_env.sh

# you're now in a virtualenv

# 'make install' will install Paperwork in the virtual environment
make install  # or 'make install_py'

# takes care of the dependencies that cannot be installed in the virtual
# environment (Gtk, Tesseract, etc)
paperwork-shell chkdeps paperwork_backend
paperwork-shell chkdeps paperwork
```

### Using the virtual environment

```sh
cd ~/git/paperwork
source ./activate_test_env.sh

# you're now in a virtualenv

# 'make install' will install Paperwork in the virtual environment
make install  # or 'make install_py'

# Running your version of Paperwork:
paperwork
```

Enjoy :-)
