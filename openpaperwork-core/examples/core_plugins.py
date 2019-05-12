#!/usr/bin/env python3

import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Start")
    core = openpaperwork_core.Core()
    core.load("openpaperwork_core.log_collector")
    core.init()
    LOGGER.info("End")


if __name__ == "__main__":
    main()
