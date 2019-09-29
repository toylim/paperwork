def _shift_pages(core, page_filename_fmt, doc_url, start_page_idx, offset):
    assert(offset != 0)

    total_pages = core.call_success("doc_get_nb_pages_by_url", doc_url)
    if total_pages is None:
        total_pages = 0

    if offset < 0:
        rng = range(start_page_idx + 1, total_pages + 1)
    elif offset > 0:
        rng = range(total_pages - 1, start_page_idx - 1, -1)

    for page_idx in rng:
        old_url = core.call_success(
            "fs_join", doc_url, page_filename_fmt.format(page_idx + 1)
        )
        if core.call_success("fs_exists", old_url) is None:
            continue
        new_url = core.call_success(
            "fs_join", doc_url, page_filename_fmt.format(
                page_idx + 1 + offset
            )
        )
        core.call_all("fs_rename", old_url, new_url)


def delete_page_file(core, page_filename_fmt, doc_url, page_idx):
    file_url = core.call_success(
        "fs_join", doc_url, page_filename_fmt.format(page_idx + 1)
    )
    if core.call_success("fs_exists", file_url) is None:
        return None
    core.call_all("fs_unlink", file_url)

    # move all the other pages 1 level down
    _shift_pages(core, page_filename_fmt, doc_url, page_idx, -1)
    return True


def move_page_file(
            core, page_filename_fmt,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        ):
    assert(core.call_success("fs_exists", dest_doc_url) is not None)

    # source_doc_url and dest_doc_url can be the same document, making
    # this change a little bit tricky. The simplest way to handle all the cases
    # is to:
    # --> move the page out of the source document (we rename it temporarily
    # page_filename_fmt.format(0))
    # --> then to insert it in the destination document

    # Move the page out of the source document
    src = core.call_success(
        "fs_join", source_doc_url,
        page_filename_fmt.format(source_page_idx + 1)
    )
    if core.call_success("fs_exists", src) is None:
        return False
    dst = core.call_success(
        "fs_join", dest_doc_url, page_filename_fmt.format(0)
    )
    core.call_all("fs_rename", src, dst)
    _shift_pages(core, page_filename_fmt, source_doc_url, source_page_idx, -1)

    # Move the page in the destination document
    src = dst
    dst = core.call_success(
        "fs_join", dest_doc_url, page_filename_fmt.format(dest_page_idx + 1)
    )
    _shift_pages(core, page_filename_fmt, dest_doc_url, dest_page_idx, 1)
    core.call_all("fs_rename", src, dst)
    return True
