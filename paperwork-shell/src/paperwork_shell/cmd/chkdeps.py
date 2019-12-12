import collections
import distro
import logging
import os
import sys

import gettext

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


PACKAGE_TOOLS = {
    'debian': 'apt-get install -y',
    'fedora': 'dnf install',
    'gentoo': 'emerge',
    'linuxmint': 'apt-get install -y',
    'ubuntu': 'apt-get install -y',
    'suse': 'zypper in',
}


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        # will call method from interface 'chkdeps', but we can still
        # work if no other plugin implement 'chkdeps'.
        return []

    def _get_distribution(self):
        distribution = distro.linux_distribution(full_distribution_name=False)
        if self.interactive:
            print("Detected system: {}".format(" ".join(distribution)))
        distribution = distribution[0].lower()
        if distribution not in PACKAGE_TOOLS:
            LOGGER.warning(
                "WARNING: Unknown distribution."
                " Can't suggest packages to install"
            )
        return distribution

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'chkdeps',
            help=_("Check that all required dependencies are installed")
        )
        p.add_argument(
            "--yes", "-y",
            required=False, default=False, action='store_true'
        )

    def cmd_run(self, args):
        if args.command != 'chkdeps':
            return None
        auto = args.yes

        if auto:
            LOGGER.warning("Confirmation disabled")

        distribution = self._get_distribution()

        missing = collections.defaultdict(dict)
        self.core.call_all("chkdeps", missing)

        if self.interactive and len(missing) > 0:
            print(_("Missing dependencies:"))
            for (dep_name, distrib_packages) in missing.items():
                print(_("- %s (package: %s)") % (
                    dep_name,
                    distrib_packages[distribution]
                    if distribution in distrib_packages
                    else _("UNKNOWN")
                ))

        if distribution in PACKAGE_TOOLS:
            command = PACKAGE_TOOLS[distribution]
            if os.getuid() != 0:
                command = "sudo {}".format(command)
        else:
            command = None
        has_pkg = False
        for (dep_name, distrib_packages) in missing.items():
            if distribution in distrib_packages:
                if command is not None:
                    command += " " + distrib_packages[distribution]
                has_pkg = True

        if self.interactive:
            if has_pkg and command is not None:
                print("")
                print(_("Suggested command:"))
                print("  " + command)
                print("")
                if not auto:
                    r = util.ask_confirmation(
                        _("Do you want to run this command now ?")
                    )
                    if r.lower() != 'y':
                        return {
                            "missing": missing,
                            "command": command,
                        }
                print("Running command ...")
                r = os.system(command)
                print("Command returned {}".format(r))
                if r != 0:
                    sys.exit(r)
            elif len(missing) > 0:
                print(
                    _("Don't know how to install missing dependencies. Sorry.")
                )
            else:
                print(_("Nothing to do."))

        return {
            "missing": missing,
            "command": command,
        }
