"""
Spatial indexer that works in a way very similar to R-tree. Except for the
way the nodes are split because I'm a lazy bastard and it's good enough.
"""


import math
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
NB_CHILDREN_PER_NODES = 2

# Node: R-tree page (leaf or not)
# Non-leaf: children are other nodes
# Leaf: last R-tree node: children are tuples (box, obj)


class Node(object):
    def __init__(self, box=None):
        self.leaf = True
        self.children = []

        self.box = None
        self.area = 0
        self.set_box(box)

        self.parent = None

    @staticmethod
    def compute_area(box):
        return abs((box[1][0] - box[0][0]) * (box[1][1] - box[0][1]))

    def compute_overlap(self, other):
        if self.box is None:
            return 0

        ours = self.box

        area_intersect = (
            (min(ours[1][0], other[1][0]) - max(ours[0][0], other[0][0]))
            * (min(ours[1][1], other[1][1]) - max(ours[0][1], other[0][1]))
        )
        other_area = self.compute_area(other)
        return self.area + other_area - area_intersect

    def set_box(self, box):
        self.box = box
        if box is None:  # root node
            self.area = math.inf
        else:
            self.area = self.compute_area(box)

    def recompute_box(self):
        if self.leaf:
            box = (
                (
                    min(x[0][0][0] for x in self.children),
                    min(x[0][0][1] for x in self.children),
                ),
                (
                    max(x[0][1][0] for x in self.children),
                    max(x[0][1][1] for x in self.children),
                ),
            )
        else:
            box = (
                (
                    min(x.box[0][0] for x in self.children),
                    min(x.box[0][1] for x in self.children),
                ),
                (
                    max(x.box[1][0] for x in self.children),
                    max(x.box[1][1] for x in self.children),
                ),
            )
        self.set_box(box)
        if self.parent is not None:
            self.parent.recompute_box()

    def is_full(self):
        assert(self.leaf)
        return len(self.children) >= NB_CHILDREN_PER_NODES

    def split(self):
        assert(self.leaf)

        # Node is full --> we need to split it
        # We should go with Guttman Quadratic algorithm
        # but for now I'm a lazy bastard
        assert(NB_CHILDREN_PER_NODES == 2)
        assert(len(self.children) == 2)
        node_a = Node(self.children[0][0])
        node_a.insert_box(self.children[0])
        node_a.parent = self
        node_b = Node(self.children[1][0])
        node_b.insert_box(self.children[1])
        node_b.parent = self
        self.children = [node_a, node_b]
        self.leaf = False

    def insert_box(self, box):
        assert(self.leaf)
        self.children.append(box)
        self.recompute_box()

    def __gt__(self, o):
        return False


class RTreeSpatialIndexer(object):
    def __init__(self, boxes):
        self.root = Node()

        for (pos, obj) in boxes:
            self.insert(pos, obj)

        self._print_stats()

    def _print_stats(self):
        """
        Not used at the moment, but useful to make sure the tree looks OK when
        debugging.
        """
        nb_boxes = 0
        nb_nodes = 0
        max_depth = 0

        to_examine = [(0, self.root)]
        while len(to_examine) > 0:
            nb_nodes += 1

            (depth, n) = to_examine.pop(0)
            max_depth = max(max_depth, depth)

            if n.leaf:
                nb_boxes += len(n.children)
            else:
                for c in n.children:
                    to_examine.append((depth + 1, c))

        LOGGER.info(
            "Rtree: %d boxes, %d nodes, max depth: %d",
            nb_boxes, nb_nodes, max_depth
        )

    def _find_leaf(self, box_position, root=None):
        if root is None:
            n = self.root
        else:
            n = root
        while not n.leaf:
            # keep picking up the child node that overlap as much of
            # box_position as possible
            n = max({
                (c.compute_overlap(box_position), c)
                for c in n.children
            })[1]
        return n

    def insert(self, box_position, box):
        new_child = (box_position, box)
        leaf = self._find_leaf(box_position)
        if leaf.is_full():
            leaf.split()
            leaf = self._find_leaf(box_position, leaf)
        leaf.insert_box(new_child)

    @staticmethod
    def is_in(box_position, pt_x, pt_y):
        if box_position[0][0] > pt_x:
            return False
        if box_position[0][1] > pt_y:
            return False
        if box_position[1][0] < pt_x:
            return False
        if box_position[1][1] < pt_y:
            return False
        return True

    def get_boxes(self, pt_x, pt_y):
        """
        Returns all the boxes that contains the point (pt_x, pt_y)
        """
        to_examine = [self.root]
        while len(to_examine) > 0:
            n = to_examine.pop(0)
            if not n.leaf:
                for c in n.children:
                    if self.is_in(c.box, pt_x, pt_y):
                        to_examine.append(c)
            else:
                for c in n.children:
                    if self.is_in(c[0], pt_x, pt_y):
                        yield (c[0], c[1])


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'spatial_index'
        ]

    def spatial_indexer_get(self, boxes):
        return RTreeSpatialIndexer(boxes)
