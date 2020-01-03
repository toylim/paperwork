# Introduction

This README explains how to install Paperwork using Flatpak.

Flatpak is a package manager for Linux. It is available on any GNU/Linux
distribution. It also keeps applications and all their dependencies inside
containers, making them easy to update and uninstall.

Its advantages:

- You get the latest version of Paperwork, directly from its developers.
- Paperwork remains nicely packaged. It won't make a mess on your system.

Its drawback:

- Using Flatpak, Paperwork comes directly from its developers. It has not been
  reviewed by your distribution maintainers. It may not include some changes
  that your distribution maintainers would have added.


# i386 and ARM architectures

[Continous integration](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/pipelines)
only builds Paperwork for amd64 (aka x86\_64). If you want to run Paperwork on i386 or arm, you can use the
[Flathub version](https://flathub.org/apps/details/work.openpaper.Paperwork).

If you don't know what architecture your computer is based and if it has more
than 2GB of RAM, you can probably ignore this chapter and keep reading.


# Quick start

## Debian >= jessie / Ubuntu >= 16.04

```sh
# Install Flatpak and Saned
sudo apt install flatpak sane-utils

# Enable Saned (required for scanning ; allow connection from the loopback only)
sudo sh -c "echo 127.0.0.1 >> /etc/sane.d/saned.conf"
sudo systemctl enable saned.socket
sudo systemctl start saned.socket

# Install Paperwork (for the current user only)
flatpak --user install https://builder.openpaper.work/paperwork_master.flatpakref

# Start Paperwork
flatpak run work.openpaper.Paperwork
```

## Fedora 28

```sh
# Install Saned
sudo dnf install sane-backends-daemon

# Enable Saned (required for scanning ; allow connection from the loopback only)
sudo sh -c "echo 127.0.0.1 >> /etc/sane.d/saned.conf"
sudo systemctl enable saned.socket
sudo systemctl start saned.socket

# Install Paperwork (for the current user only)
flatpak --user install https://builder.openpaper.work/paperwork_master.flatpakref

# Start Paperwork
flatpak run work.openpaper.Paperwork
```

# Updating Paperwork

```sh
flatpak --user update work.openpaper.Paperwork
```

# Details

## Saned

When installed using Flatpak, Paperwork runs in a container. This container prevents
Paperwork from accessing devices directly. Therefore the scanning daemon
[Saned](https://linux.die.net/man/1/saned) must be enabled on the host system,
and connection must be allowed from 127.0.0.1.


## Continuous builds

For the continuous builds based on the branch 'master' (usually contains the latest
release with some extra minor bugfixes):

```shell
flatpak --user install https://builder.openpaper.work/paperwork_master.flatpakref
```

For the continous builds based on the branch 'develop' (you can install both master
and develop if you wish):

```shell
flatpak --user install https://builder.openpaper.work/paperwork_develop.flatpakref
```


## Releases

'release' always points to the latest Paperwork release.

```shell
flatpak --user install https://builder.openpaper.work/paperwork_release.flatpakref
```


## Running Paperwork

Flatpak adds automatically a shortcut to your system menu.

You can also run it from the command line:

```shell
flatpak run work.openpaper.Paperwork
```

You can run specifically the branch 'master':

```shell
flatpak run work.openpaper.Paperwork//master
```

You can also run specifically the branch 'develop':

```shell
flatpak run work.openpaper.Paperwork//develop
```


## Build

```shell
git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork/flatpak
flatpak --user remote-add --if-not-exists gnome https://sdk.gnome.org/gnome.flatpakrepo
flatpak --user install gnome org.gnome.Sdk//3.26
flatpak --user install gnome org.gnome.Platform//3.26
make
```


## Uninstallation

Uninstallation *won't* delete your work directory nor your documents.

```ahell
flatpak --user uninstall work.openpaper.Paperwork
```


## FAQ

### How do I run paperwork-shell ?

When using Flatpak, paperwork-shell remains available. Note that it will run
inside Paperwork's container and may not access files outside your home
directory.

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork [args]
flatpak run --command=paperwork-shell work.openpaper.Paperwork --help
```

Examples:

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork help import
flatpak run --command=paperwork-shell work.openpaper.Paperwork -bq import ~/tmp/pdf
```


### How do I update The GPG public key of the Flatpak repository ?

Paperwork repository GPG key expires every 2 years. When that happens, when you
try updating Paperwork, you will get an output similar to the following one:

```
$ flatpak --user update
Looking for updates…
F: Error updating remote metadata for 'paperwork-origin': GPG signatures found, but none are in trusted keyring
F: Warning: Treating remote fetch error as non-fatal since runtime/work.openpaper.Paperwork.Locale/x86_64/master is already installed: Unable to load summary from remote paperwork-origin: GPG signatures found, but none are in trusted keyring
F: Warning: Can't find runtime/work.openpaper.Paperwork.Locale/x86_64/master metadata for dependencies: Unable to load metadata from remote paperwork-origin: summary fetch error: GPG signatures found, but none are in trusted keyring
F: Warning: Treating remote fetch error as non-fatal since app/work.openpaper.Paperwork/x86_64/master is already installed: Unable to load summary from remote paperwork-origin: GPG signatures found, but none are in trusted keyring
F: Warning: Can't find app/work.openpaper.Paperwork/x86_64/master metadata for dependencies: Unable to load metadata from remote paperwork-origin: summary fetch error: GPG signatures found, but none are in trusted keyring
(...)
Warning: org.freedesktop.Platform.openh264 needs a later flatpak version
Error: GPG signatures found, but none are in trusted keyring
Error: GPG signatures found, but none are in trusted keyring
Changes complete.
error: There were one or more errors
```

The simplest way to fix that is to reinstall Paperwork. Uninstalling Paperwork
will never delete your documents.

```
flatpak --user remove work.openpaper.Paperwork
flatpak --user install https://builder.openpaper.work/paperwork_master.flatpakref
```


### No text appears when rendering PDF files. What do I do ?

If you run Paperwork from a terminal, you can see the message
`some font thing has failed` every time you open a PDF file from Paperwork.
This issue is related to fontconfig cache.

To fix it:

- Stop Paperwork
- Run: `flatpak run --command=fc-cache work.openpaper.Paperwork -f`


### The scanner is not found

If it works with Simple-scan or with Paperwork outside of Flatpak, it probably
means it's a permission problem.

The Sane daemon (saned) runs as the user `saned`, not as your user. Therefore
the default udev rules may not set the appropriate permissions.

#### Fujitsu scanners

```
sudo adduser saned plugdev
```

#### Other scanners

```
sudo adduser saned scanner
```

You can find the instructions to fix the permissions using udev on the
[ArchLinux wiki](https://wiki.archlinux.org/index.php/SANE#Permission_problem).
