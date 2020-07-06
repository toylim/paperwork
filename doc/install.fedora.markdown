# Paperwork installation on GNU/Linux Fedora

# Paperwork installation on GNU/Linux Debian or GNU/Linux Ubuntu


## Packages

This is the recommended method of installation.

A package is available in [Fedora](https://apps.fedoraproject.org/packages/).

```sh
sudo dnf install paperwork
```

Once installed, you can run `paperwork-cli chkdeps`
and `paperwork-gtk chkdeps` to make sure all the required
depencies are installed.

You can start Paperwork with the command `paperwork-gtk`.


## Flatpak

If you want more up-to-date versions of Paperwork, you can install it
[using Flatpak](install.flatpak.markdown). Just beware that those versions of
Paperwork come directly from Paperwork developers themselves and haven't been
reviewed by the Fedora package maintainer(s).


## Reporting a bug

If you find a bug in the version of Paperwork packaged in GNU/Linux Fedora:

- First try to reproduce it with the version of Paperwork in Flatpak.
- If you can reproduce it with the Flatpak version, please
  [report it on Paperwork bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/issues)
- If you can't reproduce it with the Flatpak version, please
  [report it to the Fedora package maintainer(s)](https://fedoraproject.org/wiki/Bugzilla)
