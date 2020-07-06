Uninstallation *won't* delete your work directory nor your documents.


# Paperwork uninstallation using Flatpak

If you installed Paperwork using Flatpak, you can uninstall it with:

```sh
flatpak --user uninstall work.openpaper.Paperwork
```

# Paperwork uninstallation using virtual-env

If you installed Paperwork using Python's virtualenv
(`source ./active_test_env.sh`), you can simply delete the Git repository
(`rm -rf ~/git/paperwork`).
