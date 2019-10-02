import datetime
import logging
import time

import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


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

    def __init__(self, core, name, new_all, old_all, transaction):
        self.core = core
        self.name = name
        self.new_all = new_all
        self.old_all = old_all
        self.transaction = transaction
        self.diff_generator = None
        self.diff = set()
        self.start = None
        self.nb_compared = 0

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.run
        )

    def run(self):
        self.start = time.time()
        self.diff_generator = diff_lists(self.old_all, self.new_all)

        while True:
            try:
                diff = next(self.diff_generator)
                self.diff.add(diff)
            except StopIteration:
                break

        while len(self.diff) > 0:
            (action, key) = self.diff.pop()
            self.nb_compared += 1
            if action != 'unchanged':
                self.core.call_one(
                    "schedule", self.core.call_all,
                    "on_sync", self.name, action, key
                )
            if action == "added":
                self.transaction.add_obj(key)
            elif action == "updated":
                self.transaction.upd_obj(key)
            elif action == "deleted":
                self.transaction.del_obj(key)
            else:
                self.transaction.unchanged_obj(key)

        self.transaction.commit()
        stop = time.time()
        LOGGER.info(
            "Has compared %d objects in %.3fs",
            self.nb_compared, stop - self.start
        )
