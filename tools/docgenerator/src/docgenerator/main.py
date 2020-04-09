import datetime
import random
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402

import openpaperwork_core  # noqa: E402
import paperwork_backend  # noqa: E402
import paperwork_backend.docimport  # noqa: E402
import paperwork_backend.model.workdir  # noqa: E402
import paperwork_shell.main  # noqa: E402

from . import img  # noqa: E402
from . import pdf  # noqa: E402
from . import pdf_img  # noqa: E402


DOC_GENERATORS = {
    'pdf': (pdf.generate, ".pdf", 1),
    'img': (img.generate, ".jpeg", 2),
    'pdf_img': (pdf_img.generate, ".pdf", 1),
}


def get_core():
    core = openpaperwork_core.Core()
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()
    core.call_all("init_logs", "docgenerator", 'debug')

    core.call_all(
        "config_load", "paperwork2", "docgenerator",
        paperwork_shell.main.DEFAULT_CLI_PLUGINS
    )
    return core


def get_page_size():
    paper_size = Gtk.PaperSize.new("iso_a4")
    return (
        paper_size.get_width(Gtk.Unit.POINTS),
        paper_size.get_height(Gtk.Unit.POINTS)
    )


def main_generate_one():
    if len(sys.argv) <= 2:
        print("Usage:")
        print("  {} <type> <out_file>".format(sys.argv[0]))
        sys.exit(1)

    core = get_core()
    paper_size = get_page_size()

    file_out = core.call_success("fs_safe", sys.argv[2])
    DOC_GENERATORS[sys.argv[1]][0](core, file_out, paper_size)


def generate_doc_id(core):
    while True:
        year = random.randint(1900, 2100)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 50)
        dt = datetime.datetime(
            year=year, month=month, day=day,
            hour=hour, minute=minute, second=second
        )
        doc_id = dt.strftime(paperwork_backend.model.workdir.DOCNAME_FORMAT)
        doc_url = core.call_success("doc_id_to_url", doc_id)
        if doc_url is None:
            return doc_id
        nb_pages = core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None or nb_pages <= 0:
            return doc_id


def main_generate_workdir():
    if len(sys.argv) <= 2:
        print("Usage:")
        print("  {} <work_dir> <nb_docs>".format(sys.argv[0]))
        sys.exit(1)

    generators = ([DOC_GENERATORS['img']] * 5)
    generators += [DOC_GENERATORS['pdf_img']]
    generators += ([DOC_GENERATORS['pdf']] * 5)

    core = get_core()
    paper_size = get_page_size()

    work_dir = core.call_success("fs_safe", sys.argv[1])
    nb_docs = int(sys.argv[2])

    core.call_all("cmd_set_interactive", False)

    print("Creating {}...".format(work_dir))
    core.call_success("fs_mkdir_p", work_dir)

    print("Switching work directory to {} ...".format(work_dir))
    core.call_all("config_put", "workdir", work_dir)

    promises = []
    core.call_all("sync", promises)
    promise = promises[0]
    for p in promises[1:]:
        promise = promise.then(p)
    core.call_one("mainloop_schedule", promise.schedule)
    core.call_all("mainloop_quit_graceful")
    core.call_one("mainloop")

    for doc_idx in range(0, nb_docs):
        (generator, file_ext, nb_files) = generators[
            doc_idx % len(generators)
        ]

        if nb_files > 1:
            nb_files = int(random.expovariate(1 / 50))
            if nb_files <= 0:
                nb_files = 1
            if nb_files > 200:
                nb_files = 200

        tmp_files = []

        try:
            for f in range(0, nb_files):
                (tmp_file, tmp_fd) = core.call_success(
                    "fs_mktemp", "paperwork-docgenerator",
                    file_ext, on_disk=True
                )
                tmp_fd.close()
                tmp_files.append(tmp_file)
                print(
                    "Generating file {}/{} for document {}/{}"
                    " --> {}...".format(
                        f, nb_files, doc_idx, nb_docs, tmp_file
                    )
                )
                generator(core, tmp_file, paper_size, f, nb_files)

            file_import = paperwork_backend.docimport.FileImport(
                tmp_files, active_doc_id=None
            )

            importers = []
            core.call_all("get_importer", importers, file_import)
            print("Importers: {}".format(importers))
            assert(len(importers) > 0)
            importer = importers[0]

            promise = importer.get_import_promise()
            print("Importing {} ...".format(tmp_files))
            core.call_one("mainloop_schedule", promise.schedule)
            core.call_all("mainloop_quit_graceful")
            core.call_one("mainloop")

            print("Imported doc ids: {}".format(file_import.new_doc_ids))

            for source_doc_id in file_import.new_doc_ids:
                dest_doc_id = generate_doc_id(core)
                print("Renaming document {} --> {} ...".format(
                    source_doc_id, dest_doc_id
                ))

                source_doc_url = core.call_success(
                    "doc_id_to_url", source_doc_id
                )
                dest_doc_url = core.call_success(
                    "doc_id_to_url", dest_doc_id
                )

                core.call_all(
                    "doc_rename_by_url", source_doc_url, dest_doc_url
                )

                transactions = []
                core.call_all("doc_transaction_start", transactions, 2)
                transactions.sort(
                    key=lambda transaction: -transaction.priority
                )
                for transaction in transactions:
                    transaction.del_obj(source_doc_id)
                for transaction in transactions:
                    transaction.add_obj(dest_doc_id)
                for transaction in transactions:
                    transaction.commit()

        finally:
            print("Deleting {} ...".format(tmp_files))
            for f in tmp_files:
                core.call_success("fs_unlink", f)

        print()
