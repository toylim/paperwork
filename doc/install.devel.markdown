# Paperwork development installation

## Dependencies

Depending on which
[branch](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Branches)
you are working, the build and runtime dependencies may not be the same.
Setuptools and ```paperwork-shell chkdeps``` should take care of all of them.


## Paperwork in a Python Virtualenv

This is the recommended approach for development. If you intend to work on
Paperwork (or just try it), this is probably the most convenient way to
install safely a development version of Paperwork.

Virtualenv allows to run Paperwork in a specific environment, with the latest
versions of most of its dependencies. It also make it easier to remove it (you
just have to delete the directory containing the virtualenv). However the user
that did the installation will be the only one able to run Paperwork. No
shortcut will be installed in the menus of your window manager. Paperwork
won't be available directly on your PATH.


### Requirements

You will have to install [python-virtualenv](https://pypi.python.org/pypi/virtualenv).


### Installation

Libinsane is scan library required by Paperwork. You need it in your
development environment. Paperwork Makefile can take of that for you.


```sh
mkdir -p ~/git
cd ~/git

git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork
git checkout develop  # or 'master', 'release-xxx', 'wip-xxx', etc

# Create the Python virtualenv.
# Compile Libinsane and set the correct environment variables to use it
# without installing it.
make venv

# active\_test\_env.sh sets environment variables so you can use Libinsane
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


### Note regarding the extra dependencies

Many dependencies can't be installed from Pypi or in a virtualenv. For
instance, all the libraries accessed through GObject introspection have
no package on Pypi. This is why they can only be installed in a system-wide
manner.

'paperwork-shell chkdeps paperwork_backend' and
'paperwork-shell chkdeps paperwork' can find all the missing dependencies.


### Running Paperwork

```sh
cd ~/git/paperwork
source ./activate_test_env.sh
paperwork
```

Enjoy :-)
