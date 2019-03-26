# Paperwork development installation

## Dependencies

Depending on which
[branch](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Branches)
you are working, the build and runtime dependencies may not be the same.
Setuptools and ```paperwork-shell chkdeps``` should take care of all of them.


## System-wide installation

```sh
mkdir -p ~/git
cd ~/git
git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
git checkout develop  # or 'release-xxx'

# will run 'python3 ./setup.py install' on all Paperwork components
sudo make install  # or 'make install_py'

# install non-Python dependencies
paperwork-shell chkdeps paperwork_backend
paperwork-shell chkdeps paperwork

# if you want to add it in the menus
paperwork-shell install
```

(see [the wiki as to why you probably want to work on the branch
'develop'](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Branches))


## Paperwork in a Python Virtualenv

If you intend to work on Paperwork, this is probably the most convenient way
to install safely a development version of Paperwork.

Virtualenv allows to run Paperwork in a specific environment, with the latest
versions of most of its dependencies. It also make it easier to remove it (you
just have to delete the directory containing the virtualenv). However the user
that did the installation will be the only one able to run Paperwork. No
shortcut will be installed in the menus of your window manager. Paperwork
won't be available directly on your PATH.


### Requirements

You will have to install [python-virtualenv](https://pypi.python.org/pypi/virtualenv).


### Installation

```sh
git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork
git checkout develop  # or 'release-xxx'

virtualenv --system-site-packages -p python3 venv
source venv/bin/activate
# you're now in a virtualenv

make install  # or 'make install_py'

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
source venv/bin/activate
paperwork
```

Enjoy :-)
