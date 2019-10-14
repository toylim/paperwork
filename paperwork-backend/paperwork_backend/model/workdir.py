import datetime
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"

    def get_interfaces(self):
        return ["document_storage"]

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio']),
                ('paperwork_config', ['paperwork_backend.config.file']),
            ]
        }

    def storage_get_all_docs(self, out: list):
        """
        Returns all document IDs and URLs in the work directory
        """
        workdir = self.core.call_success('paperwork_config_get', 'workdir')
        if self.core.call_success('fs_exists', workdir) is None:
            # we are not the plugin handling this work directory (?)
            return
        LOGGER.info("Loading document list from %s", workdir)
        nb = 0
        for doc_url in self.core.call_success('fs_listdir', workdir):
            if self.core.call_success("is_doc", doc_url) is None:
                continue
            out.append((
                self.core.call_success("fs_basename", doc_url), doc_url
            ))
            nb += 1
        LOGGER.info("%d documents found in %s", workdir)

    def doc_id_to_url(self, doc_id):
        workdir = self.core.call_success('paperwork_config_get', 'workdir')
        return self.core.call_success("fs_join", workdir, doc_id)

    def doc_url_to_id(self, doc_url):
        workdir = self.core.call_success('paperwork_config_get', 'workdir')
        if not doc_url.startswith(workdir):
            return None
        return self.core.call_success("fs_basename", doc_url)

    def doc_get_date_by_id(self, doc_id):
        # Doc id is expected to have this format:
        # YYYYMMDD_hhmm_ss_NN_something_else
        doc_id = doc_id.split("_", 3)
        doc_id = "_".join(split[:3])
        try:
            return datetime.datetime.strptime(doc_id, self.DOCNAME_FORMAT)
        except ValueError:
            return None

    # datetime.datetime.now cannot be mocked with unittest.mock.patch
    # (datetime is built-in) --> allow dependency injection here
    def storage_get_new_doc(self, now_func=datetime.datetime.now):
        workdir = self.core.call_success('paperwork_config_get', 'workdir')

        base_doc_id = now_func().strftime(self.DOCNAME_FORMAT)
        base_doc_url = self.core.call_success("fs_join", workdir, base_doc_id)

        doc_id = base_doc_id
        doc_url = base_doc_url
        doc_idx = 0

        while self.core.call_success("fs_exists", doc_url) is not None:
            doc_idx += 1
            doc_id = "{}_{}".format(base_doc_id, doc_idx)
            doc_url = "{}_{}".format(base_doc_url, doc_idx)

        # reserve the doc_id by creating the directory
        self.core.call_all("fs_mkdir_p", doc_url)

        return (doc_id, doc_url)
