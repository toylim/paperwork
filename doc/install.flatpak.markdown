# Introduction

Flatpak is a package manager for Linux. It is available on all major GNU/Linux
distributions. It also keeps applications and all their dependencies inside
containers, making them easy to update and uninstall.

Its advantages:

- You get the latest version of Paperwork, directly from its developers.
- Paperwork remains nicely packaged. It won't make a mess on your system.

Its drawback:

- Using Flatpak, Paperwork comes directly from its developers. It has not been
  reviewed by your distribution maintainers. It may not include some changes
  that your distribution maintainers would have added.


# Quick start

## Installing Flatpak

* GNU/Linux Debian: `sudo apt install flatpak`
* GNU/Linux Fedora: `sudo dnf install flatpak`


## Installing Paperwork

```sh
# Install Paperwork (for the current user only)
# <branch> can be:
# - 'master': stable branch (latest release + some bug fixes)
# - 'testing': stabilization branch
# - 'develop': development branch (new untested features)
flatpak --user install https://builder.openpaper.work/paperwork_<branch>.flatpakref

# For example:
flatpak --user install https://builder.openpaper.work/paperwork_master.flatpakref
```

Flatpak will add a Paperwork icon in your menus. You may have to log out and
log back in to see it.

Alternatively, you can start Paperwork from a terminal:

```sh
flatpak run work.openpaper.Paperwork
```


## Allowing Paperwork to access scanners

When installed using Flatpak, Paperwork runs in a container. This container prevents
Paperwork from accessing devices directly. Therefore the scanning daemon
[Saned](https://linux.die.net/man/1/saned) must be enabled on the host system,
and connection must be allowed from 127.0.0.1.

Instructions can be found in the settings of Paperwork:

![Flatpak + Saned instructions: Step 1](flatpak_saned_1.png)
![Flatpak + Saned instructions: Step 2](flatpak_saned_2.png)
![Flatpak + Saned instructions: Step 3](flatpak_saned_3.png)


## Updating Paperwork

```sh
flatpak --user update work.openpaper.Paperwork
```

# FAQ

## How do I run paperwork-cli / paperwork-json ?

When using Flatpak, paperwork-cli is also available. Note that it will run
inside Paperwork's container and cannot access files outside your home
directory.

```sh
flatpak run --command=paperwork-cli work.openpaper.Paperwork [args]
flatpak run --command=paperwork-cli work.openpaper.Paperwork --help
```

Examples:

```sh
flatpak run --command=paperwork-cli work.openpaper.Paperwork help import
flatpak run --command=paperwork-cli work.openpaper.Paperwork -bq import ~/tmp/pdf
```


## No text appears when rendering PDF files. What do I do ?

If you run Paperwork from a terminal, you can see the message
`some font thing has failed` every time you open a PDF file from Paperwork.
This issue is related to fontconfig cache.

To fix it:

- Stop Paperwork
- Run: `flatpak run --command=fc-cache work.openpaper.Paperwork -f`


## What about i386 and ARM architectures ?

[Continous integration](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/pipelines)
only builds Paperwork for amd64 (aka x86\_64). If you want to run Paperwork
on i386 or ARM systems, you can use the
[Flathub version](https://flathub.org/apps/details/work.openpaper.Paperwork).

If you don't know what architecture your computer is based and if your computer
has more than 2GB of RAM, it is probably compatible with amd64.


## How do I update The GPG public key of the Flatpak repository ?

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


# Build

Here are the instructions if you want to try to build the Flatpak version
yourself.

```sh
git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork/flatpak
flatpak --user remote-add --if-not-exists gnome https://sdk.gnome.org/gnome.flatpakrepo
flatpak --user install gnome org.gnome.Sdk//3.26
flatpak --user install gnome org.gnome.Platform//3.26
make
```
