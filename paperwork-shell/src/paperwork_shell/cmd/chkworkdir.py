try:
    # Fabulous is available and installed on GNU/Linux systems, but not on
    # Windows. Still this command can be called on Windows systems using
    # "paperwork-json"
    import fabulous
    import fabulous.color
    FABULOUS_AVAILABLE = True
except (ImportError, ValueError):
    FABULOUS_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.cmd.util

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'chkworkdir',
                'defaults': [
                    'paperwork_backend.chkworkdir.empty_doc',
                    'paperwork_backend.chkworkdir.label_color',
                ],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'chkworkdir', help=_("Check and fix work directory integrity")
        )
        p.add_argument(
            '--yes', '-y', required=False, default=False, action='store_true',
            help=_("Don't ask to fix things, just fix them")
        )

    @staticmethod
    def _color(color):
        assert FABULOUS_AVAILABLE
        color = "#%1X%1X%1X" % (
            int(color[0] * 0xF),
            int(color[1] * 0xF),
            int(color[2] * 0xF),
        )
        return fabulous.color.bg256(color, "  ") + " "

    def cmd_run(self, console, args):
        if args.command != 'chkworkdir':
            return None

        console.print(_("Checking work directory ..."))

        problems = []
        self.core.call_all("check_work_dir", problems)

        if len(problems) <= 0:
            console.print(_("No problem found"))
            return problems

        console.print("")
        console.print(_("%d problems found:") % len(problems))
        for problem in problems:
            problem_color = (
                ""
                if "problem_color" not in problem
                else self._color(problem['problem_color'])
            )
            solution_color = (
                ""
                if "solution_color" not in problem
                else self._color(problem['solution_color'])
            )

            console.print("[{}]".format(problem['problem']))
            console.print(
                _("- Problem: ") + problem_color +
                problem['human_description']['problem']
            )
            console.print(
                _("- Possible solution: ") + solution_color +
                problem['human_description']['solution']
            )
            console.print("")

        if not args.yes:
            msg = _(
                "Do you want to fix those problems automatically"
                " using the indicated solutions ?"
            )
            r = openpaperwork_core.cmd.util.ask_confirmation(
                console,
                msg,
                default_interactive='n',
                default_non_interactive='n',
            )
            if r != 'y':
                console.print("OK, nothing changed.")
                return problems

        console.print(_("Fixing ..."))
        self.core.call_all("fix_work_dir", problems)
        console.print(_("All fixed !"))
        console.print(_("Synchronizing with work directory ..."))

        self.core.call_all("transaction_sync_all")
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        console.print(_("All done !"))

        return problems
