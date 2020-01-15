def parse_page_list(args):
    if not hasattr(args, 'pages'):
        return None
    if args.pages is None or args.pages == "":
        return None

    if "-" in args.pages:
        pages = args.pages.split("-", 1)
        return range(
            int(pages[0]) - 1,
            int(pages[1])
        )
    else:
        return [
            (int(p) - 1) for p in args.pages.split(",")
            if int(p) >= 1
        ]
