import itertools


def delete_page_file(core, doc_url, page_filename_fmt, page_idx):
    file_url = core.call_success(
        "fs_join", doc_url, page_filename_fmt.format(page_idx + 1)
    )
    if core.call_success("fs_exists", file_url) is None:
        return None
    core.call_all("fs_unlink", file_url)

    # move all the other pages 1 level down
    for page_idx in itertools.count(page_idx + 1):
        old_url = core.call_success(
            "fs_join", doc_url, page_filename_fmt.format(page_idx + 1)
        )
        new_url = core.call_success(
            "fs_join", doc_url, page_filename_fmt.format(page_idx)
        )
        if not core.call_success("fs_exists", old_url):
            break

        core.call_all("fs_rename", old_url, new_url)
    return True
