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
