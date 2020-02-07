import datetime
import logging
import time

import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class BaseTransaction(object):
    def __init__(self, core, total_expected):
        self.core = core
        self.processed = 0
        self.total = total_expected

    def notify_progress(self, upd_type, description):
        if self.total <= self.processed:
            self.total = self.processed + 1
        if self.total <= 0:
            progression = 0
        else:
            progression = self.processed / self.total

        self.core.call_one(
            "mainloop_schedule", self.core.call_all,
            "on_progress", upd_type, progression, description
        )

    def notify_done(self, upd_type):
        self.core.call_one(
            "mainloop_schedule", self.core.call_all,
            "on_progress", upd_type, 1.0
        )

    def add_obj(self, doc_id):
        self.processed += 1

    def upd_obj(self, doc_id):
        self.processed += 1

    def del_obj(self, doc_id):
        self.processed += 1

    def unchanged_obj(self, doc_id):
        self.processed += 1

    def cancel(self):
        pass

    def commit(self):
        pass


def diff_lists(list_old, list_new):
    """
    Returns a dictionary giving the differences between both lists.

    Objects in the list must have 2 attributes:
    - `key`
    - `extra`

    `key` values identify each object in both lists.
    Comparisons are done on `key` + `extra`.

    `list_old` will be unrolled immediately.

    Arguments:
        `list_old` -- [a, b, c, ...]
        `list_new` -- [a, c_modified, d, ...]

    Returns:
        [
            ('same', a.key),
            ('del', b.key),
            ('upd', c.key),
            ('add', d.key),
        ]

        list_old + diff => list_new
    """
    list_old = {obj.key: obj for obj in list_old}
    examined_new = set()

    for obj_new in list_new:
        examined_new.add(obj_new.key)

        if obj_new.key not in list_old:
            yield ('added', obj_new.key)
            continue

        obj_old = list_old[obj_new.key]
        if obj_new.extra != obj_old.extra:
            yield ('updated', obj_new.key)
        else:
            yield ('unchanged', obj_new.key)

    for obj_old in list_old.values():
        if obj_old.key not in examined_new:
            yield ('deleted', obj_old.key)


class StorageDoc(object):
    def __init__(self, core, doc_id, doc_url):
        self.core = core
        self.key = doc_id
        self.doc_url = doc_url

    def get_mtime(self):
        mtime = []
        self.core.call_all(
            'doc_get_mtime_by_url', mtime, self.doc_url
        )
        return datetime.datetime.fromtimestamp(max(mtime, default=0))

    extra = property(get_mtime)


class Syncer(object):
    """
    This object allows to compare mtimes progressively. It then calls
    the methods `add`, `del`, `upd` and `commit` on the given object
    `transaction`.
    """

    def __init__(self, core, names, new_all, old_all, transactions):
        self.core = core
        self.names = names
        self.new_all = new_all
        self.old_all = old_all
        self.transactions = transactions
        self.diff_generator = None
        self.start = None
        self.nb_compared = 0

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.run
        )

    def run(self):
        self.start = time.time()
        self.diff_generator = diff_lists(self.old_all, self.new_all)

        try:
            for (action, key) in self.diff_generator:
                LOGGER.info("Sync: %s, %s", action, key)
                self.nb_compared += 1
                if action != 'unchanged':
                    for name in self.names:
                        self.core.call_one(
                            "mainloop_schedule", self.core.call_all,
                            "on_sync", name, action, key
                        )
                if action == "added":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.add_obj<%s>(%s)",
                            transaction.add_obj, key
                        )
                        transaction.add_obj(key)
                elif action == "updated":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.upd_obj<%s>(%s)",
                            transaction.upd_obj, key
                        )
                        transaction.upd_obj(key)
                elif action == "deleted":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.del_obj<%s>(%s)",
                            transaction.del_obj, key
                        )
                        transaction.del_obj(key)
                else:
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.unchanged_obj<%s>(%s)",
                            transaction.unchanged_obj, key
                        )
                        transaction.unchanged_obj(key)

            LOGGER.info("Sync: Committing ...")
            for transaction in self.transactions:
                transaction.commit()
            LOGGER.info("Sync: Committed")
            stop = time.time()
            LOGGER.info(
                "%s: Has compared %d objects in %.3fs",
                self.names, self.nb_compared, stop - self.start
            )
        except Exception as exc:
            LOGGER.error(
                "%s: Fail to sync. Cancelling transactions",
                self.names, exc_info=exc
            )
            for transaction in self.transactions:
                transaction.cancel()
