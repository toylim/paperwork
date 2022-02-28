# Reporting bug

If you want open a ticket on Gitlab, the following information is needed:
- Exact Paperwork version
- Operation system (Windows ? Linux ?)
- If you use Linux: how did you install Paperwork ? Using Flatpak ?
- Logs of the session where the bug happened are strongly recommended.
- If the bug is a UI bug, a screenshot is strongly recommended.

# Other contributions

[You can help in many ways](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Contributing):
- [Code contributions](doc/install.devel.markdown)
- UX and UI designs ([example](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/issues/356#note_244099))
- Testing
- [Translating](https://translations.openpaper.work)
- Documentation (markdown files or [LyX](https://www.lyx.org/)/[PDF files](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/paperwork-gtk/doc)
  integrated in Paperwork)

For most tasks, being familiar with Git is really helpful.

Most of the communication happens on the
[bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/issues)
or on the [forum](https://forum.openpaper.work/)
Sometimes [IRC](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Contact#irc) is used too.


# Code contribution

[OpenPaperwork-core documentation](https://doc.openpaper.work/openpaperwork_core/latest/index.html)

Rules are:

* All commits go to the branch `develop`. I (Jflesch) will cherry-pick them in the branches `master` (stable) or `testing` (release) if required.
* Paperwork is made to be *simple* to use (think simple enough that your own mother could install and use it)
* Paperwork is open-source software (GPLv3+)
* Run `make check` and `make test`. If they fail, your changes will be rejected.
* Consider adding automated tests.
* Consider updating the user manual
  (paperwork-gtk/src/paperwork\_gtk/model/help/data/\*.tex)
* Your changes must respect the [PEP8](https://www.python.org/dev/peps/pep-0008/): you can use the command `make check` to check your changes
* You must not break existing features.
* You're strongly encouraged to discuss the changes you want to make beforehand (on the bug tracker, on the forum or on IRC).
* Your contribution must be maintainable: It must be clear enough so that somebody else can maintain it. If it is a complicated piece of code, please comment it as clearly as possible.
* Your contribution must and will be reviewed (most likely by me, Jflesch)
* If you make an important contribution, please try to maintain it (fix bugs reported by other users regarding features you added, etc).
* Unmaintained and unmaintainable pieces of code will be removed, sooner or later.
* [Please try to have one change per commit](https://www.freshconsulting.com/atomic-commits/).
* If you see pieces of code that doesn't follow these rules, feel free to make a cleanup commit to fix it. Please do not mix cleanups with other changes in a same commit.
* If you add new dependencies, please update:
  * setup.py scripts as required (beware of Windows support)
  * `chkdeps()` methods as required
  * Flatpak JSON files as required

Same rules apply for all the libraries in Openpaperwork: PyOCR, Libinsane, etc.

Regarding PEP-8, the following rules must be strictly followed:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces


# Continous Integration and Delivery

There is a [Continous Integration and Delivery](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/pipelines) running.
All changes must leave the CI/CD OK. You can have look at the file
.gitlab-ci.yml to know what the CI/CD build and check.


# Branches

Paperwork follows a process similar to the [GitFlow branching model](http://nvie.com/posts/a-successful-git-branching-model/).

Permanent branches:
* `master` : always match the last released version of Paperwork + some extra bugfixes. Only documentation updates and **safe** bugfixes are allowed on this branch. Minor versions come from this branch.
  Please **do not** send me changes for the branch 'master'. Send them for the branch `develop`, and I will cherry-pick them on `master` if required.
* `develop` : where new features, cleanup, etc go.
* `testing` : the next version of Paperwork, during its testing phase. No new feature is allowed. Only bugfixes, translations and documentation updates.
  When no new version is being prepared, it simply matches the branch `master`. (Those pre-release branches should be called `release-xxx`, but here it's
  called `testing` to simplify CI/CD management)

Temporary / feature development branches:
* `wip-xxxx`

Bug fixes and other contributions always go first in the branch `develop`.
They may or may not be cherry-picked into the branches `testing` and `master` by
Paperwork maintainer (Jerome Flesch).

# Main dependencies

Paperwork depends on various libraries:

* GLib, Cairo, GTK, etc: GUI
* Poppler: Reading PDF
* Pillow: Reading images, basic operations on images, writing images
* [PyOCR](https://gitlab.gnome.org/World/OpenPaperwork/pyocr):
  Wrapper for Tesseract + Parsing and writing of hOCR files
* [Libpillowfight](https://gitlab.gnome.org/World/OpenPaperwork/libpillowfight):
  Various image processing algorithms
* [Libinsane](https://gitlab.gnome.org/World/OpenPaperwork/libinsane):
  Crossplatform access to scanners

# General code structure

Paperwork is divided in many Python packages:

* openpaperwork-core:
  - The [core](https://doc.openpaper.work/openpaperwork_core/latest) is the piece
    of code that manages the plugins. It's designed to be as minimal as possible.
  - Various plugins who could be useful in pretty much any other application,
   GUI or not (for instance, [Pythoness](https://framagit.org/OpenPaperwork/pythoness)).
* openpaperwork-gtk:
  - Various plugins who could be useful in pretty much any Gnome/GTK application
    (for instance, [Pythoness](https://framagit.org/OpenPaperwork/pythoness)).
* paperwork-backend:
  - Plugins for Paperwork independant from any type of frontends (plugins to manage the
    work directory, provide various features, access scanners, etc)
* paperwork-gtk:
  - Plugins and bootstrap module that compose the GTK user interface of Paperwork
* paperwork-shell:
  - Plugins and bootstrap module that compose the shell interface (CLI or JSON)

# Tips

## Virtual env

You can easily get a Python virtual environment that includes OpenPaperwork
dependencies (Libinsane, ...) by using the script `activate_test_env.sh`:

```sh
make clean  # delete any previously existing virtual env
source ./activate_test_env.sh  # build and load a virtual env
make install # install Paperwork and its Python dependencies in the virtual env
paperwork-gtk
```


## Debug

On GNU/Linux, you can increase debug level by using the following command:

```sh
paperwork-gtk config put log_level str debug
```

Or, if you use Flatpak:

```sh
flatpak run --command=paperwork-gtk work.openpaper.Paperwork config put log_level str debug
```

You can revert the log level by setting it back to `info` instead of `debug`.


## Separate Paperwork configuration for development from your day-to-day configuration

If you want to make changes, here is a tip that can help you:

Paperwork looks for a file `paperwork2.conf` in the current work directory before
looking for a `~/.config/paperwork2.conf` in your home directory. So if you want to
use a different configuration and/or a different set of documents for development
than for your real-life work, just copy your `~/.config/paperwork2.conf` to
`./paperwork2.conf`. Note that the settings dialog will also take care of
updating `./paperwork2.conf` instead of `~/.config/paperwork2.conf` if it exists.


# Versionning

Version have the following syntax: &lt;M&gt;[.&lt;m&gt;[.&lt;U&gt;[-&lt;extra&gt;]]]

## M = Major version

Major changes made / product completed.

On libraries, it means completely incompatible API with the previous version.

## m = minor version

Minor changes made.

On libraries, it means new major features have been added, but API should remain compatible.

## U = update version

Only bugfixes or very minor features.


## Extra

May match a Git tag done before a big change (for instance: before switching from Gtk 2 to Gtk 3).
If extra == "git", indicates a version directly taken from the git repository.
