# Paperwork installation on GNU/Linux Gentoo

## Packages

This is the recommended method of installation.

A package is [available in GNU/Linux Gentoo](https://packages.gentoo.org/packages/app-text/paperwork).

```sh
sudo emerge paperwork
```

Once installed, you can run `paperwork-cli chkdeps`
and `paperwork-gtk chkdeps` to make sure all the required
depencies are installed.

You can start Paperwork with the command `paperwork-gtk`.

## Flatpak

If you want more up-to-date versions of Paperwork, you can install it
[using Flatpak](install.flatpak.markdown). Just beware that those versions of
Paperwork come directly from Paperwork developers themselves and haven't been
reviewed by the Gentoo package maintainer(s).


## Reporting a bug

If you find a bug in the version of Paperwork packaged in GNU/Linux Gentoo:

- First try to reproduce it with the version of Paperwork in Flatpak.
- If you can reproduce it with the Flatpak version, please
  [report it on Paperwork bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/issues)
- If you can't reproduce it with the Flatpak version, please
  [report it to the Gentoo package maintainer(s)](https://wiki.gentoo.org/wiki/Bugzilla/Bug_report_guide)
