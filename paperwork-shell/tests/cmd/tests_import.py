import argparse
import os
import shutil
import tempfile
import unittest

import openpaperwork_core
import openpaperwork_core.cmd
import openpaperwork_core.fs


class TestSync(unittest.TestCase):
    def setUp(self):
        self.console = openpaperwork_core.cmd.DummyConsole()

        self.test_pdf = "{}/test_doc.pdf".format(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.tmp_local_dir = tempfile.mkdtemp()
        self.tmp_work_dir = tempfile.mkdtemp()
        os.environ['XDG_DATA_HOME'] = self.tmp_local_dir

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.init()

        self.work_dir_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_work_dir
        )
        config = self.core.get_by_name("openpaperwork_core.config.fake")
        config.settings = {
            "workdir": self.work_dir_url,
        }

    def tearDown(self):
        self.core.call_all("tests_cleanup")
        shutil.rmtree(self.tmp_local_dir)
        shutil.rmtree(self.tmp_work_dir)

    def test_import_pdf_with_specific_doc_id_1046(self):
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_shell.cmd.import")
        self.core.init()

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args([
            'import', '--doc_id', '29991010_1212_33', self.test_pdf
        ])
        self.core.call_all(
            "cmd_set_console", openpaperwork_core.cmd.DummyConsole()
        )
        r = self.core.call_success("cmd_run", self.console, args)
        self.assertEqual(r['ignored'], [])
        self.assertEqual(r['imported'], [self.core.call_success(
            "fs_safe", self.test_pdf
        )])
        self.assertEqual(r['new_docs'], ['29991010_1212_33'])
        self.assertEqual(r['upd_docs'], [])

        self.assertTrue(self.core.call_success(
            "fs_exists", self.core.call_success(
                "fs_join", self.core.call_success(
                    "fs_join", self.work_dir_url, "29991010_1212_33"
                ), "doc.pdf"
            )
        ))
