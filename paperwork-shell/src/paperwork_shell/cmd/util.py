import gettext
import sys


_ = gettext.gettext


def ask_confirmation(question, default='y'):
    sys.stdout.write(question)

    if default == 'y':
        yesno = _("Y/n")
        default = yesno[0].lower()
    else:
        yesno = _("y/N")
        default = yesno[-1].lower()

    sys.stdout.write(" [{}] ".format(yesno))

    reply = input()
    if reply == "":
        reply = default
    else:
        reply = reply.lower()

    return 'y' if reply == yesno[0].lower() else 'n'


def parse_page_list(args):
    if not hasattr(args, 'pages'):
        return None
    if args.pages is None or args.pages == "":
        return None

    if "-" in args.pages:
        pages = args.pages.split("-", 1)
        return range(
            int(pages[0]) - 1,
            min(int(pages[1]), nb_pages)
        )
    else:
        return [
            (int(p) - 1) for p in args.pages.split(",")
            if int(p) >= 1
        ]
