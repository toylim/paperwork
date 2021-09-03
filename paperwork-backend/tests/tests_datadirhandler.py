import shutil
import tempfile
import unittest
import os

import openpaperwork_core
from paperwork_backend.model import workdir


class TestDirHandler(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )
        #self.xdg_old = os.getenv("XDG_DATA_HOME", self.tmp_paperwork_dir)
        #os.environ["XDG_DATA_HOME"] = self.tmp_paperwork_dir

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.datadirhandler")
        self.core.load("openpaperwork_core.paths.xdg")
        self.core.load("openpaperwork_core.config")

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )
        self.datadirhandler = self.core.get_by_name(
            "paperwork_backend.datadirhandler"
        )
        self.paperwork_temp_data = tempfile.mkdtemp(
            prefix="paperwork_temp_data"
        )
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.beacon.stats")

        self.core.init()

        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: self.paperwork_temp_data
        )

        self.core.call_success(
            "config_register", "workdir", setting)

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)
        shutil.rmtree(self.paperwork_temp_data)

    def test_init(self):
        data_dir_hashed = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed))
        self.datadirhandler._delete_old_directories(
            days_to_data_dir_deletion=2)
        # after deleting old directories with the default value,
        # the created directory should still be there
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed))
        self.datadirhandler._delete_old_directories(
            days_to_data_dir_deletion=0)
        self.assertFalse(self.core.call_success("fs_exists", data_dir_hashed))

    def test_dir_hash(self):
        data_dir_hashed = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed),
                        "directory %s should exist but it does not" % data_dir_hashed)
        workdir = self.core.call_success('config_get', 'workdir')
        self.assertEqual(os.path.basename(workdir), os.path.basename(
            data_dir_hashed[:-9]))

        data_dir_wo_hash = self.core.call_success("paths_get_data_dir")
        self.assertEqual(os.path.commonprefix(
            [data_dir_wo_hash, data_dir_hashed]), data_dir_wo_hash)

        data_dir_hashed_again = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertEqual(data_dir_hashed, data_dir_hashed_again)
