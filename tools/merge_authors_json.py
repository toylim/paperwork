#!/usr/bin/env python3

import json
import sys


def load_jsons(file_paths):
    out = []
    for file_path in file_paths:
        sys.stderr.write("Loading {} ...\n".format(file_path))
        with open(file_path, 'r') as fd:
            content = fd.read()
            out.append(json.loads(content))
    return out


def merge_jsons(jsons):
    sys.stderr.write("Merging ...\n")
    out = []
    for j in jsons:
        out += j
    return out


def sort_json(out):
    sys.stderr.write("Sorting ...\n")

    # keep in mind we are immitating the JSON from Weblate here, and Weblate's
    # JSON is a bit weird.

    for category in out:
        for (category_name, authors) in category.items():
            # sort authors by line count
            authors.sort(key=lambda x: x[2], reverse=True)

    # Sort categories alphabetically
    out.sort(key=lambda x: next(iter(x)).lower())


def main():
    if len(sys.argv) <= 1 or sys.argv[1] == "-h" or sys.argv[1] == "--help":
        sys.stderr.write("Syntax:\n")
        sys.stderr.write(
            "  {} <JSON file> [<JSON file> [<JSON file> ...]]\n".format(
                sys.argv[0]
            )
        )
        return

    jsons = load_jsons(sys.argv[1:])
    out = merge_jsons(jsons)
    sort_json(out)
    print(json.dumps(
        out,
        indent=4,
        separators=(',', ': '),
        sort_keys=True
    ))
    sys.stderr.write("All done !\n")


if __name__ == "__main__":
    main()
