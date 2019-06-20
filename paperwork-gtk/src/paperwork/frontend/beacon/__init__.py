import datetime
import distro
import http
import http.client
import json
import logging
import os
import platform
import ssl
import threading
import urllib


logger = logging.getLogger(__name__)


class Beacon(object):
    USER_AGENT = "Paperwork"

    UPDATE_CHECK_INTERVAL = datetime.timedelta(days=7)
    POST_STATISTICS_INTERVAL = datetime.timedelta(days=7)

    SSL_CONTEXT = ssl._create_unverified_context()

    OPENPAPERWORK_RELEASES = {
        'host': os.getenv("OPENPAPER_SERVER", 'openpaper.work'),
        'path': '/beacon/latest',
    }
    OPENPAPERWORK_STATS = {
        'host': os.getenv("OPENPAPER_SERVER", 'openpaper.work'),
        'path': '/beacon/post_statistics',
    }
    PROTOCOL = os.getenv("OPENPAPER_PROTOCOL", "https")

    def __init__(self, config, flatpak):
        super().__init__()
        self.config = config
        self.flatpak = flatpak

    def get_version_openpaperwork(self):
        logger.info("Querying OpenPaper.work ...")
        if self.PROTOCOL == "http":
            h = http.client.HTTPConnection(
                host=self.OPENPAPERWORK_RELEASES['host'],
            )
        else:
            h = http.client.HTTPSConnection(
                host=self.OPENPAPERWORK_RELEASES['host'],
                context=self.SSL_CONTEXT
            )
        h.request('GET', url=self.OPENPAPERWORK_RELEASES['path'], headers={
            'User-Agent': self.USER_AGENT
        })
        r = h.getresponse()
        r = r.read().decode('utf-8')
        r = json.loads(r)
        return r['paperwork'][os.name]

    def check_update(self):
        if not self.config['check_for_update'].value:
            logger.info("Update checking is disabled")
            return

        now = datetime.datetime.now()
        last_check = self.config['last_update_check'].value

        logger.info("Updates were last checked: {}".format(last_check))
        if (last_check is not None and
                last_check + self.UPDATE_CHECK_INTERVAL >= now):
            logger.info("No need to check for new updates yet")
            return

        logger.info("Checking for updates ...")
        version = None
        try:
            version = self.get_version_openpaperwork()
        except Exception as exc:
            logger.exception(
                "Failed to get latest Paperwork release from OpenPaper.work. ",
                exc_info=exc
            )
        if version is None:
            return

        logger.info("Latest Paperwork release: {}".format(version))
        self.config['last_update_found'].value = version
        self.config['last_update_check'].value = now
        self.config.write()

    def get_statistics(self, version, docsearch):
        if os.name == 'nt':
            distribution = platform.win32_ver()
        else:
            distribution = distro.linux_distribution(
                full_distribution_name=False
            )
        processor = ""
        os_name = os.name
        if os_name != 'nt':  # contains too much infos on Windows
            processor = platform.processor()
            if self.flatpak:
                os_name += " (flatpak)"
        return {
            'uuid': int(self.config['uuid'].value),
            'paperwork_version': str(version),
            'nb_documents': int(docsearch.nb_docs),
            'os_name': str(os_name),
            'platform_architecture': str(platform.architecture()),
            'platform_processor': str(processor),
            'platform_distribution': str(distribution),
            'cpu_count': int(os.cpu_count()),
        }

    def send_statistics(self, version, docsearch):
        if not self.config['send_statistics'].value:
            logger.info("Anonymous statistics are disabled")
            return

        now = datetime.datetime.now()
        last_post = self.config['last_statistics_post'].value

        logger.info("Statistics were last posted: {}".format(last_post))
        logger.info("Next post date: {}".format(
            last_post + self.POST_STATISTICS_INTERVAL))
        logger.info("Now: {}".format(now))
        if (last_post is not None and
                last_post + self.POST_STATISTICS_INTERVAL >= now):
            logger.info("No need to post statistics")
            return

        logger.info("Sending anonymous statistics ...")
        stats = self.get_statistics(version, docsearch)
        logger.info("Statistics: {}".format(stats))

        logger.info("Posting statistics on openpaper.work ...")
        if self.PROTOCOL == "http":
            h = http.client.HTTPConnection(
                host=self.OPENPAPERWORK_STATS['host'],
            )
        else:
            h = http.client.HTTPSConnection(
                host=self.OPENPAPERWORK_STATS['host'],
                context=self.SSL_CONTEXT
            )
        h.request('POST', url=self.OPENPAPERWORK_STATS['path'], headers={
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            'User-Agent': self.USER_AGENT,
        }, body=urllib.parse.urlencode({
            'statistics': json.dumps(stats),
        }))
        r = h.getresponse()
        logger.info("Getting reply from openpaper.work ({})".format(r.status))
        reply = r.read().decode('utf-8')
        if r.status == http.client.OK:
            logger.info("Openpaper.work replied: {} | {}".format(
                r.status, r.reason
            ))
        else:
            logger.warning("Openpaper.work replied: {} | {}".format(
                r.status, r.reason
            ))
            logger.warning("Openpaper.work: {}".format(reply))

        self.config['last_statistics_post'].value = now
        self.config.write()


def check_update(beacon):
    thread = threading.Thread(target=beacon.check_update)
    thread.start()


def send_statistics(beacon, version, docsearch):
    thread = threading.Thread(target=beacon.send_statistics, kwargs={
        'version': version,
        'docsearch': docsearch,
    })
    thread.start()
