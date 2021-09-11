import asyncio
import functools
import logging


LOGGER = logging.getLogger(__name__)


def async_cb(fn):
    """
    Simple wrapper to be able to call an async method from a non-async
    context.
    When the callback is called, the call will return immediately
    but the run of the callback will be scheduled in the event loop
    Beware that this wrapper still assumes we are called indirectly from an
    asyncio event loop (in the same thread)

    Example:

    ```
    @async_cb
    async def toto(arg):
        await something(arg)

    toto("arg")
    ```
    """
    @functools.wraps(fn)
    async def internal_wrapper(*args, **kwargs):
        try:
            await fn(*args, **kwargs)
        except Exception as exc:
            LOGGER.error("common: Uncaught exception", exc_info=exc)

    @functools.wraps(internal_wrapper)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        loop.create_task(internal_wrapper(*args, **kwargs))

    return wrapper
