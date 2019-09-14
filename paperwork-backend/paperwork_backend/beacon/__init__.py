"""
module 'beacon' contains all the code to communicate with
https://openpaper.work/
"""

import http
import http.client
import logging
import json
import urllib


LOGGER = logging.getLogger(__name__)
USER_AGENT = "Paperwork"


class OpenpaperHttp(object):
    def __init__(self, protocol, server, url):
        self.protocol = protocol
        self.server = server
        self.url = url

    def request(self, action="GET", data_name=None, data=None):
        if data_name is not None:
            data = {data_name: json.dumps(data)}

        if self.protocol == "http":
            h = http.client.HTTPConnection(host=self.server)
        else:
            h = http.client.HTTPSConnection(host=self.server)
        h.request(action, url=self.url, headers={
            'User-Agent': self.USER_AGENT
        })
        r = h.getresponse()
        r = r.read().decode('utf-8')
        r = json.loads(r)
