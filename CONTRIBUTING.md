# How to contribute ?

[You can help in many ways](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Contributing):
- [Code contributions](doc/install.devel.markdown)
- UX and UI designs ([example](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/issues/356#note_244099))
- Testing
- Translating
- Documentation (markdown files or [LyX](https://www.lyx.org/)/[PDF files](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/tree/master/paperwork-gtk/doc)
  integrated in Paperwork)

For most tasks, being familiar with Git is really helpful.

Most of the communication happens on the [bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/issues).
Sometimes the [mailing-list](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Contact#mailing-list)
or [IRC](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/wikis/Contact#irc) are used too.


# Code contribution rules

* All commits go to the branch 'develop'. I (Jflesch) will cherry-pick them in master or release branches if required.
* Paperwork is made to be *simple* to use (think simple enough that your own grandmother could install and use it)
* Paperwork is open-source software (GPLv3+)
* Your changes must respect the [PEP8](https://www.python.org/dev/peps/pep-0008/) (you can use the command `make check` to check your changes)
* You must not break existing features. You're strongly encouraged to discuss the changes you want to make beforehand (on the bug tracker, the mailing-list or IRC).
* Your contribution must be maintainable: It must be clear enough so that somebody else can maintain it. If it is a complicated piece of code, please comment it as clearly as possible.
* Your contribution must and will be reviewed (most likely by me, Jflesch)
* If you make an important contribution, please try to maintain it (fix bug reported by other users regarding features you added, etc).
* Unmaintained and unmaintainable pieces of code will be removed, sooner or later.
* [Please try to have one change per commit](https://www.freshconsulting.com/atomic-commits/).
* If you see pieces of code that doesn't follow these rules, feel free to make a cleanup commit to fix it. Please do not mix cleanups with other changes in a same commit.
* If you add new dependencies, please update:
  * `setup.py`: for Python dependencies
  * `setup_cx_freeze.py`: for the build of the Windows executable (only for the GTK interface)
  * `src/paperwork/deps.py`: frontend ; for non-Python dependencies
  * `paperwork-backend/deps.py`: backend ; for non-Python dependencies
  * `flatpak/develop.json`: Used to generate Flatpak packages (see `flatpak-builder`). To test your changes, you can generate standalone Paperwork Flatpak bundles with "cd flatpak ; make bundles" (it's quite long ; beware it will use your local `develop.json` but will package Paperwork from Github).

Same rules apply for all the libraries in Openpaperwork: PyOCR, Libinsane, etc.

Regarding PEP-8, the following rules must be strictly followed:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces

(again, please run `make check` before submitting a change)


# Continous Integration and Delivery

There is a [Continous Integration and Delivery](https://origami.openpaper.work) running.
All changes must leave the CI/CD OK.


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


# Tips


## Debug

You can use the environment variable `PAPERWORK\_VERBOSE` to increase or
decrease the logging level. The accepted values are: DEBUG, INFO, WARNING,
ERROR.


## Separate Paperwork configuration for development from your day-to-day configuration

If you want to make changes, here is a tip that can help you:

Paperwork looks for a file `paperwork.conf` in the current work directory before
looking for a `.paperwork.conf` in your home directory. So if you want to
use a different configuration and/or a different set of documents for development
than for your real-life work, just copy your `~/.paperwork.conf` to
`./paperwork.conf`. Note that the settings dialog will also take care of
updating `./paperwork.conf` instead of `~/.paperwork.conf` if it exists.


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