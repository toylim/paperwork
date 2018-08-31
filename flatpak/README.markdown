This README explains how to install Paperwork using Flatpak.
Flatpak is a package manager for Linux. It also keeps applications and all their
dependencies inside containers, making them easy to update and uninstall.


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

## Releases

'release' always points to the latest Paperwork release.

```shell
flatpak --user install https://builder.openpaper.work/paperwork_release.flatpakref
```

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

## Running paperwork-shell

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
