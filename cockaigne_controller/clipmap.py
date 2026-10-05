"""The map of nodes and the table of clips that move between them.

A node is where the wall "is": Barren (`b`), or an arm at a ring (`m1` is
Machinery ring 1). A clip's name carries its move, from-node then to-node,
with an optional underscore: `a1m1`, `b_m1` and `bm1` all parse. A name
whose two nodes are the same (`m4m4`, `b_b`) is that node's loop clip.
Names that do not parse are ignored, so the composition can hold stems and
idents without confusing the map.

The map refuses nothing by itself; `missing()` lists what a complete pool
must have, and the controller refuses to start while the list is not empty.
"""
from __future__ import annotations

from collections import deque

BARREN = "b"


def node_name(arm_letter: str, ring: int) -> str:
    return BARREN if ring == 0 else f"{arm_letter}{ring}"


def _take_node(s: str, arms: dict, rings: int) -> tuple[str, str] | None:
    """Read one node from the front of s. Returns (node, rest) or None."""
    if s.startswith(BARREN):
        return BARREN, s[1:]
    if len(s) >= 2 and s[0] in arms and s[1].isdigit() and 1 <= int(s[1]) <= rings:
        return s[:2], s[2:]
    return None


def parse_clip_name(name: str, arms: dict, rings: int) -> tuple[str, str] | None:
    """The naming rule: from-node then to-node, underscores ignored.
    Returns (from, to), or None for a name that is not a move clip."""
    core = name.strip().lower().replace("_", "")
    first = _take_node(core, arms, rings)
    if first is None:
        return None
    frm, rest = first
    second = _take_node(rest, arms, rings)
    if second is None or second[1] != "":
        return None
    return frm, second[0]


class ClipMap:
    """Built once at start-up from the clip names Resolume reports."""

    def __init__(self, clip_names: list[str], arms: dict, rings: int = 4):
        self.arms = arms
        self.rings = rings
        self.moves: dict[tuple[str, str], str] = {}   # (from, to) -> clip name
        self.loops: dict[str, str] = {}               # node -> loop clip name
        for name in clip_names:
            parsed = parse_clip_name(name, arms, rings)
            if parsed is None:
                continue
            frm, to = parsed
            if frm == to:
                self.loops.setdefault(frm, name)
            else:
                self.moves.setdefault((frm, to), name)

    def nodes(self) -> list[str]:
        return [BARREN] + [node_name(a, r) for a in self.arms for r in range(1, self.rings + 1)]

    def clip_for(self, frm: str, to: str) -> str | None:
        """The clip that carries this exact move, or this node's loop."""
        if frm == to:
            return self.loops.get(frm)
        return self.moves.get((frm, to))

    def neighbours(self, frm: str) -> list[str]:
        return [to for (f, to) in self.moves if f == frm]

    def next_step(self, frm: str, to: str) -> str | None:
        """The first hop of the shortest path through the clips that exist.
        None when no path exists (missing() will have said so at start-up)."""
        if frm == to:
            return to
        seen = {frm}
        queue = deque([(frm, None)])  # (node, first hop that reached it)
        while queue:
            node, first = queue.popleft()
            for nxt in self.neighbours(node):
                if nxt in seen:
                    continue
                hop = first or nxt
                if nxt == to:
                    return hop
                seen.add(nxt)
                queue.append((nxt, hop))
        return None

    def missing(self) -> list[str]:
        """What a complete pool must have but this one does not, in plain words.

        Required: a loop clip for every Ring 4 node, a direct collapse clip
        to Barren from every Ring 2 and Ring 3 node, and a route between
        every pair of nodes through the clips that exist.
        """
        problems = []
        for a in self.arms:
            node = node_name(a, 4)
            if node not in self.loops:
                problems.append(f"no loop clip for {node}")
            for r in (2, 3):
                if (node_name(a, r), BARREN) not in self.moves:
                    problems.append(f"no collapse clip {node_name(a, r)} to {BARREN}")
        for frm in self.nodes():
            unreachable = [to for to in self.nodes()
                           if to != frm and self.next_step(frm, to) is None]
            if unreachable:
                problems.append(f"no route from {frm} to {', '.join(unreachable)}")
        return problems
