# Paperwork installation on GNU/Linux Debian or GNU/Linux Ubuntu


## Packages

This is the recommended method of installation.

A package is [available in GNU/Linux Debian](https://packages.debian.org/search?keywords=paperwork-gtk&searchon=names&suite=all&section=all).
Since GNU/Linux Ubuntu is based on GNU/Linux Debian, [Paperwork is also available in it](https://packages.ubuntu.com/search?keywords=paperwork-gtk&searchon=names&suite=all&section=all).

```sh
# For example:
sudo apt install paperwork-gtk paperwork-gtk-l10n-fr
```

Once installed, you can run `paperwork-cli chkdeps`
and `paperwork-gtk chkdeps` to make sure all the required
depencies are installed.

You can start Paperwork with the command `paperwork-gtk`.


## Flatpak

If packages are not yet available for your version of
GNU/Linux Debian/Ubuntu/Mint/… or if you want
more up-to-date versions of Paperwork, you can install it
[using Flatpak](install.flatpak.markdown). Just beware that those versions of
Paperwork come directly from Paperwork developers themselves and haven't been
reviewed by the Debian package maintainer(s).


## Reporting a bug

If you find a bug in the version of Paperwork packaged in GNU/Linux Debian:

- First try to reproduce it with the version of Paperwork in Flatpak.
- If you can reproduce it with the Flatpak version, please
  [report it on Paperwork bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/issues)
- If you can't reproduce it with the Flatpak version, please
  [report it to the Debian package maintainer(s)](https://www.debian.org/Bugs/)
