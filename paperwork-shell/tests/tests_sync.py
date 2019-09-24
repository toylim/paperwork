import argparse
import datetime
import os
import shutil
import tempfile
import unittest

import openpaperwork_core


class TestSync(unittest.TestCase):
    def setUp(self):
        self.test_img = "{}/test_img.jpeg".format(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.test_hocr = "{}/test_txt.hocr".format(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.test_pdf = "{}/test_doc.pdf".format(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.tmp_local_dir = tempfile.mkdtemp()
        self.tmp_work_dir = tempfile.mkdtemp()
        os.environ['XDG_DATA_HOME'] = self.tmp_local_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_local_dir)
        shutil.rmtree(self.tmp_work_dir)
        os.unsetenv('XDG_DATA_HOME')

    def test_sync(self):
        core = openpaperwork_core.Core()
        core.load("paperwork_backend.config.fake")
        core.init()
        config = core.get_by_name("paperwork_backend.config.fake")
        config.settings = {
            "workdir": "file://" + self.tmp_work_dir,
        }

        core.load("paperwork_backend.model.img")
        core.load("paperwork_backend.model.hocr")
        core.load("paperwork_backend.model.pdf")
        core.load("paperwork_shell.sync")
        core.init()

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(['sync'])
        core.call_all("cmd_set_interactive", False)

        # start with an empty work directory

        r = core.call_success("cmd_run", args)
        self.assertEqual(r, {})

        # add 2 documents, one PDF and one img+hocr

        doc_a = os.path.join(self.tmp_work_dir, "20190801_1733_23")
        os.mkdir(doc_a)
        shutil.copyfile(self.test_pdf, os.path.join(doc_a, "doc.pdf"))

        doc_b = os.path.join(self.tmp_work_dir, "20190830_1916_32")
        os.mkdir(doc_b)
        shutil.copyfile(self.test_img, os.path.join(doc_b, "paper.1.jpg"))
        shutil.copyfile(self.test_hocr, os.path.join(doc_b, "paper.1.words"))

        r = core.call_success("cmd_run", args)
        self.assertEqual(r, {
            'whoosh': {
                'added': ['20190801_1733_23', '20190830_1916_32',],
            },
            'label_guesser': {
                'added': ['20190801_1733_23', '20190830_1916_32',],
            }
        })

        # modify one document

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 9999999999
                def fs_get_mtime(s, file_url):
                    if file_url.endswith(".words"):
                        dt = datetime.datetime(year=2222, month=1, day=1)
                        return dt.timestamp()
                    return None

        core._load_module("fake_module", FakeModule())
        core.init()

        r = core.call_success("cmd_run", args)
        self.assertEqual(r, {
            'whoosh': {
                'updated': ['20190830_1916_32',],
            },
            'label_guesser': {
                'updated': ['20190830_1916_32',],
            }
        })

        # delete one document

        shutil.rmtree(doc_a)

        r = core.call_success("cmd_run", args)
        self.assertEqual(r, {
            'whoosh': {
                'deleted': ['20190801_1733_23',],
            },
            'label_guesser': {
                'deleted': ['20190801_1733_23',],
            }
        })
