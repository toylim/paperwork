"""
module 'beacon' contains all the code to communicate with
https://openpaper.work/
"""

import datetime
import http
import http.client
import logging
import json
import urllib

from .. import _version

import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
USER_AGENT = "Paperwork " + _version.version


class PeriodicTask(object):
    def __init__(
                self, config_section_name, min_delay: datetime.timedelta,
                periodic_callback, else_callback=lambda: None
            ):
        self.config_section_name = config_section_name
        self.min_delay = min_delay
        self.periodic_callback = periodic_callback
        self.else_callback = else_callback

    def register_config(self, core):
        setting = core.call_success(
            "paperwork_config_build_simple", self.config_section_name,
            "last_run", lambda: datetime.date(year=1970, month=1, day=1)
        )
        core.call_all(
            "paperwork_config_register",
            self.config_section_name + "_last_run",
            setting
        )

    def do(self, core):
        now = datetime.date.today()
        last_run = core.call_success(
            "paperwork_config_get", self.config_section_name + "_last_run"
        )
        LOGGER.info(
            "[%s] Last run: %s ; Now: %s",
            self.config_section_name, last_run, now
        )
        if now - last_run < self.min_delay:
            LOGGER.info(
                "[%s] Nothing to do (%s < %s)",
                self.config_section_name, now - last_run, self.min_delay
            )
            self.else_callback()
            return

        LOGGER.info(
            "[%s] Running %s (%s >= %s)",
            self.config_section_name,
            self.periodic_callback, now - last_run, self.min_delay
        )
        self.periodic_callback()

        LOGGER.info("[%s] Updating last run date", self.config_section_name)


class OpenpaperHttp(object):
    def __init__(
                self, config_section_name, default_protocol, default_server,
                default_url
            ):
        self.config_section_name = config_section_name
        self.default_protocol = default_protocol
        self.default_server = default_server
        self.default_url = default_url

    def register_config(self, core):
        settings = {
            self.config_section_name + "_protocol":
                core.call_success(
                    "paperwork_config_build_simple", self.config_section_name,
                    "protocol", lambda: self.default_protocol
                ),
            self.config_section_name + "_server":
                core.call_success(
                    "paperwork_config_build_simple", self.config_section_name,
                    "server", lambda: self.default_protocol
                ),
            self.config_section_name + "_url":
                core.call_success(
                    "paperwork_config_build_simple", self.config_section_name,
                    "url", lambda: self.default_url
                ),
        }
        for (k, setting) in settings.items():
            core.call_all("paperwork_config_register", k, setting)

    def _request(self, data, protocol, server, url):
        if protocol == "http":
            h = http.client.HTTPConnection(host=server)
        else:
            h = http.client.HTTPSConnection(host=server)

        if data is None or data == "":
            h.request('GET', url=url, headers={'User-Agent': USER_AGENT})
        else:
            body = urllib.parse.urlencode({
                k: json.dumps(v)
                for (k, v) in data.items()
            })
            h.request(
                'POST', url=url, headers={
                    "Content-type": "application/x-www-form-urlencoded",
                    "Accept": "text/plain",
                    'User-Agent': USER_AGENT,
                },
                body=body
            )
        r = h.getresponse()
        reply = r.read().decode('utf-8')
        if r.status != http.client.OK:
            raise ConnectionError("HTTP {}: {} - {}".format(
                r.status, r, reply
            ))
        if reply[0] != '[' and reply[0] != '{':
            return
        return json.loads(reply)

    def get_request_promise(self, core):
        protocol = core.call_success(
            "paperwork_config_get", self.config_section_name + "_protocol"
        )
        server = core.call_success(
            "paperwork_config_get", self.config_section_name + "_server"
        )
        url = core.call_success(
            "paperwork_config_get", self.config_section_name + "_url"
        )

        return openpaperwork_core.promise.ThreadedPromise(
            core, self._request, args=(protocol, server, url)
        )
