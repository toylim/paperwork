import itertools
import logging

try:
    import gi
    gi.require_version('Libinsane', '1.0')
    from gi.repository import GObject
    GI_AVAILABLE = True
except ImportError:
    GI_AVAILABLE = False

try:
    from gi.repository import Libinsane
    LIBINSANE_AVAILABLE = True
except ImportError:
    LIBINSANE_AVAILABLE = False

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)

SCAN_ID_GENERATOR = itertools.count()


class LibinsaneLogger(GObject.GObject, Libinsane.Logger):
    LEVELS = {
        Libinsane.LogLevel.DEBUG: LOGGER.debug,
        Libinsane.LogLevel.INFO: LOGGER.info,
        Libinsane.LogLevel.WARNING: LOGGER.warning,
        Libinsane.LogLevel.ERROR: LOGGER.error,
    }

    min_level = Libinsane.LogLevel.DEBUG

    def do_log(self, lvl, msg):
        if lvl < self.min_level:
            return
        self.LEVELS[lvl]("[LibInsane] " + msg)


def raw_to_img(params, img_bytes):
    fmt = params.get_format()
    assert(fmt == Libinsane.ImgFormat.RAW_RGB_24)
    (w, h) = (
        params.get_width(),
        int(len(img_bytes) / 3 / params.get_width())
    )
    mode = "RGB"
    return PIL.Image.frombuffer(mode, (w, h), img_bytes, "raw", mode, 0, 1)


class ImageAssembler(object):
    MIN_CHUNK_SIZE = 128 * 1024

    def __init__(self, line_width):
        # 'Pieces' are pieces of the images that may or may not contain
        # full lines of pixels (or even partial pixel)

        # 'chunk': We want to provide the GUI with a preview of the scan.
        # To keep things simple, we provide chunk of the image and those
        # chunk must contain only entire lines of pixels.

        # and then we must also provide the whole image at the end.

        self.w = line_width  # in bytes

        self.current_piece = []
        self.all_chunks = []

    def add_piece(self, piece):
        self.current_piece.append(piece)
        lcurrent_piece = sum((len(c) for c in self.current_piece))
        if lcurrent_piece < self.w or lcurrent_piece < self.MIN_CHUNK_SIZE:
            return

        current_piece = b"".join(self.current_piece)
        chunkable = lcurrent_piece - (lcurrent_piece % self.w)
        new_chunk = current_piece[:chunkable]
        new_piece = current_piece[chunkable:]

        self.all_chunks.append(new_chunk)
        if len(new_piece) <= 0:
            self.current_piece = []
        else:
            self.current_piece = [new_piece]

    def get_last_chunk(self):
        if len(self.all_chunks) <= 0:
            return None
        return self.all_chunks[-1]

    def get_image(self):
        return b"".join(self.all_chunks) + b"".join(self.current_piece)


class Source(object):
    def __init__(self, core, scanner, source):
        self.core = core
        self.scanner = scanner
        self.source_id = source.get_name()
        self.source = source

    def __str__(self):
        return "{}:{}".format(str(self.scanner), self.source_id)

    def set_as_default(self):
        self.core.call_all(
            "paperwork_config_put", "scanner_source_id", self.source_id
        )

    def get_resolutions(self):
        LOGGER.info(
            "Looking for possible values for option 'resolution' on %s"
            " : %s ...", str(self.scanner), self.source_id
        )
        options = self.source.get_options()
        options = {opt.get_name(): opt for opt in options}

        opt = options['resolution']
        constraint = opt.get_constraint()
        LOGGER.info(
            "%s : %s : resolution : Possible values: %s",
            str(self.scanner), self.source_id, constraint
        )
        return constraint

    def get_resolutions_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.get_resolutions
        )

    def set_default_resolution(self, resolution):
        self.core.call_all(
            "paperwork_config_put", "scanner_resolution", int(resolution)
        )

    def scan(
                self, scan_id=None, resolution=None, max_pages=9999,
                close_on_end=False
            ):
        if scan_id is None:
            scan_id = next(SCAN_ID_GENERATOR)

        LOGGER.info("Setting scan options ...")
        if resolution is None:
            resolution = self.core.call_success(
                "paperwork_config_get", "scanner_resolution"
            )
        options = self.source.get_options()
        opts = {opt.get_name(): opt for opt in options}
        if 'resolution' in opts:
            opts['resolution'].set_value(resolution)

        imgs = self._scan(scan_id, resolution, max_pages, close_on_end)
        return (self, scan_id, imgs)


    def _scan(self, scan_id, resolution, max_pages, close_on_end=False):
        # keep in mind that we are in a thread here, but listeners
        # must be called from the main loop

        LOGGER.info("Scanning ...")

        try:
            page_nb = 0

            self.core.call_one(
                "schedule", self.core.call_all,
                "on_scan_feed_start", scan_id
            )

            session = self.source.scan_start()

            while not session.end_of_feed() and page_nb < max_pages:
                scan_params = session.get_scan_parameters()
                LOGGER.info(
                    "Expected scan parameters: %s ; %dx%d = %d bytes",
                    scan_params.get_format(),
                    scan_params.get_width(), scan_params.get_height(),
                    scan_params.get_image_size()
                )
                self.core.call_one(
                    "schedule", self.core.call_all,
                    "on_scan_page_start", scan_id, page_nb, scan_params
                )

                assert(
                    scan_params.get_format()
                    == Libinsane.ImgFormat.RAW_RGB_24
                )
                image = ImageAssembler(scan_params.get_width() * 3)
                last_chunk = None

                LOGGER.info("Scanning page %d/%d ...", page_nb, max_pages)
                while not session.end_of_page():
                    new_piece = session.read_bytes(64 * 1024).get_data()
                    image.add_piece(new_piece)

                    chunk = image.get_last_chunk()
                    if chunk is not last_chunk:
                        last_chunk = chunk
                        self.core.call_one(
                            "schedule", self.core.call_all,
                            "on_scan_chunk", scan_id, scan_params,
                            raw_to_img(scan_params, chunk)
                        )

                LOGGER.info("Page %d/%d scanned", page_nb, max_pages)
                img = raw_to_img(scan_params, image.get_image())
                yield img
                self.core.call_one(
                    "schedule", self.core.call_all,
                    "on_scan_page_end", scan_id, page_nb, img
                )
                page_nb += 1
            LOGGER.info("End of feed")

            self.core.call_one(
                "schedule", self.core.call_all, "on_scan_feed_end", scan_id
            )
        finally:
            session.cancel()
            if close_on_end:
                self.close()

    def scan_promise(self, *args, scan_id=None, **kwargs):
        if scan_id is None:
            scan_id = next(SCAN_ID_GENERATOR)
        kwargs['scan_id'] = scan_id
        return (
            scan_id,
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self.scan, args=args, kwargs=kwargs
            )
        )

    def close(self, *args, **kwargs):
        self.scanner.close()
        # return the args for convience when used with promises
        if len(args) == 1 and len(kwargs) == 0:
            return args
        return (args, kwargs)


class Scanner(object):
    def __init__(self, core, scanner):
        self.core = core
        self.dev_id = scanner.get_name()
        self.dev = scanner

    def __str__(self):
        return self.dev_id

    def __del__(self):
        self.close()

    def close(self, *args, **kwargs):
        if self.dev is not None:
            LOGGER.info("Closing device %s", self.dev_id)
            self.dev.close()
            self.dev = None
        # return the args for convenience when used with promises
        if len(args) == 1 and len(kwargs) == 0:
            return args
        return (args, kwargs)

    def get_sources(self):
        LOGGER.info("Looking for scan sources on %s ...", self.dev_id)
        sources = self.dev.get_children()
        sources = [
            Source(self.core, self.dev, source)
            for source in sources
        ]
        sources = {
            source.source_id: source
            for source in sources
        }
        LOGGER.info("%d sources found: %s", len(sources), sources)
        return sources

    def get_sources_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.get_sources
        )

    def get_source(self, source_id):
        return self.get_sources()[source_id]

    def set_as_default(self):
        self.core.call_all(
            "paperwork_config_put", "scanner_dev_id",
            'libinsane:' + self.dev_id
        )


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        LOGGER.info("Initializing Libinsane ...")
        self.libinsane_logger = LibinsaneLogger()
        Libinsane.register_logger(self.libinsane_logger)
        self.libinsane = Libinsane.Api.new_safebet()
        LOGGER.info("Libinsane %s initialized", self.libinsane.get_version())

    def get_interfaces(self):
        return [
            "chkdeps",
            "scan"
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('mainloop', ['openpaperwork_core.mainloop_asyncio']),
                ('paperwork_config', ['paperwork_backend.config.file']),
            ]
        }

    def init(self, core):
        super().init(core)

        settings = {
            'scanner_dev_id': self.core.call_success(
                "paperwork_config_build_simple", "scanner",
                "dev_id", lambda: None
            ),
            'scanner_source_id': self.core.call_success(
                "paperwork_config_build_simple", "scanner",
                "source", lambda: None
            ),
            'scanner_resolution': self.core.call_success(
                "paperwork_config_build_simple", "scanner",
                "resolution", lambda: 300
            ),
        }
        for (k, setting) in settings.items():
            self.core.call_all(
                "paperwork_config_register", k, setting
            )

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi']['debian'] = 'python3-gi'
            out['gi']['fedora'] = 'python3-gobject-base'
            out['gi']['gentoo'] = 'dev-python/pygobject'  # Python 3 ?
            out['gi']['linuxmint'] = 'python3-gi'
            out['gi']['ubuntu'] = 'python3-gi'
            out['gi']['suse'] = 'python-gobject'  # Python 3 ?
        if not LIBINSANE_AVAILABLE:
            out['gi.repository.Libinsane'] = {}

    def scan_list_scanners_promise(self):
        def list_scanners(*args, **kwargs):
            LOGGER.info("Looking for scan devices ...")
            devs = self.libinsane.list_devices(Libinsane.DeviceLocations.ANY)
            devs = [
                # (id, human readable name)
                # prefix the IDs with 'libinsane:' so we know it comes from
                # our plugin and not another scan plugin
                ('libinsane:' + dev.get_dev_id(), dev.to_string())
                for dev in devs
            ]
            LOGGER.info("%d devices found: %s", len(devs), devs)
            return devs

        return openpaperwork_core.promise.ThreadedPromise(
            self.core, list_scanners
        )

    def scan_get_scanner_promise(self, scanner_dev_id):
        if not scanner_dev_id.startswith("libinsane:"):
            return None
        scanner_dev_id = scanner_dev_id[len("libinsane:"):]

        def get_scanner(*args, **kwargs):
            LOGGER.info("Accessing scanner '%s' ...", scanner_dev_id)
            scanner = self.libinsane.get_device(scanner_dev_id)
            LOGGER.info("Scanner '%s' opened", scanner.get_name())
            return Scanner(self.core, scanner)

        return openpaperwork_core.promise.ThreadedPromise(
            self.core, get_scanner
        )

    def scan_promise(self, *args, **kwargs):
        scanner_dev_id = self.core.call_success(
            "paperwork_config_get", "scanner_dev_id"
        )
        source_id = self.core.call_success(
            "paperwork_config_get", "scanner_source_id"
        )
        scan_id = next(SCAN_ID_GENERATOR)

        promise = self.scan_get_scanner_promise(scanner_dev_id)
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, Scanner.get_source, args=(source_id,)
            )
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, Source.scan, args=(scan_id,), kwargs={
                    'close_on_end': True
                }
            )
        )

        return (scan_id, promise)
