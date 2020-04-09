#!/usr/bin/env python3

import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Start")
    core = openpaperwork_core.Core()
    core.load("openpaperwork_core.logs.print")
    core.load("openpaperwork_core.uncaught_exception")
    core.load('openpaperwork_core.config')
    core.load('openpaperwork_core.config.backend.configparser')
    core.init()
    core.init_logs("some_app_name", default_log_level="info")
    LOGGER.info("End")


if __name__ == "__main__":
    main()
