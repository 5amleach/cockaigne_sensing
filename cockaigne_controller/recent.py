"""No quick returns: the wall does not go back to a node it showed a few minutes ago.

Sam, 28 Nov 2026: Friday's and Saturday's visitors saw the same places come
round again within minutes. This remembers when the wall last arrived at each
node and calls a node "recent" while that was less than `minutes` ago. Barren
is never recent, because an empty room must always be able to go back to it.
A window of 0 turns the rule off.

The rule never overrides the crowd's ring: a climb or a descent goes ahead
even to a recent node (Controller._fresh_instead in loop.py). Each ring has
eight nodes and every clip runs one minute, so with a window of eight minutes
or more a ring held that long has no node left that was not shown recently;
the controller then takes the one shown longest ago, which tours the eight
axes in turn.
"""
from __future__ import annotations

from .clipmap import BARREN


class Recent:
    def __init__(self, minutes: float):
        self.window_s = 60.0 * minutes
        self.clear()

    def clear(self) -> None:
        """Day start: yesterday's visits do not block today."""
        self.arrived: dict[str, float] = {}

    def arrive(self, node: str, t: float) -> None:
        """The wall is now showing this node."""
        self.arrived[node] = t

    def is_recent(self, node: str, now: float) -> bool:
        if self.window_s <= 0 or node == BARREN or node not in self.arrived:
            return False
        return now - self.arrived[node] < self.window_s

    def last_arrived(self, node: str) -> float:
        """When the wall last arrived here; never shown counts as longest ago."""
        return self.arrived.get(node, float("-inf"))
