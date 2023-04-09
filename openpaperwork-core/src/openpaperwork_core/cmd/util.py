from .. import _


def ask_confirmation(
            console, question,
            default_interactive='n', default_non_interactive='n'
        ):
    if default_interactive == 'y':
        yesno = _("Y/n")
    else:
        yesno = _("y/N")
    if default_interactive == 'y':
        default_interactive = yesno[0].lower()  # l10n
    else:
        default_interactive = yesno[-1].lower()  # l10n
    if default_non_interactive == 'y':
        default_non_interactive = yesno[0].lower()  # l10n
    else:
        default_non_interactive = yesno[-1].lower()  # l10n

    try:
        reply = console.input(f"{question} [{yesno}] ")
    except KeyboardInterrupt:
        return 'n'
    if reply is None:
        reply = default_non_interactive
    else:
        reply = reply.strip().lower()
        if reply == "":
            reply = default_interactive

    return 'y' if reply == yesno[0].lower() else 'n'
