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
    def __init__(self):
        super().__init__()
        self.interactive = False

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

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

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
        assert(FABULOUS_AVAILABLE)
        color = "#%1X%1X%1X" % (
            int(color[0] * 0xF),
            int(color[1] * 0xF),
            int(color[2] * 0xF),
        )
        return fabulous.color.bg256(color, "  ") + " "

    def cmd_run(self, args):
        if args.command != 'chkworkdir':
            return None

        if self.interactive:
            print(_("Checking work directory ..."))

        problems = []
        self.core.call_all("check_work_dir", problems)

        if len(problems) <= 0:
            if self.interactive:
                print(_("No problem found"))
            return problems

        if not args.yes:
            if not self.interactive:
                return problems
            print("")
            print(_("%d problems found:") % len(problems))
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

                print("[{}]".format(problem['problem']))
                print(
                    _("- Problem: ") + problem_color +
                    problem['human_description']['problem']
                )
                print(
                    _("- Possible solution: ") + solution_color +
                    problem['human_description']['solution']
                )
                print("")

            msg = _(
                "Do you want to fix those problems automatically"
                " using the indicated solutions ?"
            )
            r = openpaperwork_core.cmd.util.ask_confirmation(msg, default='n')
            if r != 'y':
                return problems

        self.core.call_all("fix_work_dir", problems)
        if self.interactive:
            print(_("All fixed !"))
            print(_("Synchronizing with work directory ..."))

        self.core.call_all("transaction_sync_all")
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        if self.interactive:
            print(_("All done !"))

        return problems
