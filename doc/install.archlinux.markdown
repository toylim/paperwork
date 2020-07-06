# Paperwork installation on GNU/Linux ArchLinux


## Packages

This is the recommended method of installation.

A package is available in [AUR](https://www.archlinux.org/packages/community/any/paperwork/).

Once installed, you can run `paperwork-cli chkdeps`
and `paperwork-gtk chkdeps` to make sure all the required
depencies are installed.

You can start Paperwork with the command `paperwork-gtk`.


## Flatpak

You can get more up-to-date versions of Paperwork
[using Flatpak](install.flatpak.markdown). Just beware that those versions of
Paperwork come directly from Paperwork developers themselves and haven't been
reviewed by the ArchLinux package maintainer(s).


## Reporting a bug

If you find a bug in the version of Paperwork packaged in GNU/Linux ArchLinux:

- First try to reproduce it with the version of Paperwork in Flatpak.
- If you can reproduce it with the Flatpak version, please
  [report it on Paperwork bug tracker](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/issues)
- If you can't reproduce it with the Flatpak version, please
  [report it to the ArchLinux package maintainer(s)](https://wiki.archlinux.org/index.php/Bug_reporting_guidelines)
