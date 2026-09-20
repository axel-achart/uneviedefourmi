# Une vie de fourmi : anthill model, optimal scheduling and drawing.
#
# Anthill file format:
#   f=5         -> number of ants in the colony
#   S1          -> a room holding a single ant
#   S2 { 4 }    -> a room holding 4 ants at the same time
#   Sv - S1     -> a tunnel between the vestibule and room 1

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

VESTIBULE = "Sv"
DORMITORY = "Sd"

# Room spacing on the drawings: one column is one step away from the vestibule.
COLUMN_SPACING = 1.6
ROW_SPACING = 1.2

# f=5 / F=100
_ANTS_PATTERN = re.compile(r"^[fF]\s*=\s*(\d+)$")
# S2 { 4 }  or  S2
_ROOM_PATTERN = re.compile(r"^(S\w+)\s*(?:\{\s*(\d+)\s*\})?$")
# Sv - S1
_TUNNEL_PATTERN = re.compile(r"^(S\w+)\s*-\s*(S\w+)$")

# Endpoints of the time expanded network used by the solver.
_SOURCE = "source"
_SINK = "sink"


@dataclass
class Room:
    name: str
    capacity: float = 1

    @property
    def is_unlimited(self) -> bool:
        return self.capacity == math.inf

    def __str__(self) -> str:
        if self.is_unlimited:
            return self.name
        return f"{self.name}{{{int(self.capacity)}}}"


@dataclass
class Anthill:
    name: str = "anthill"
    ant_count: int = 0
    rooms: dict[str, Room] = field(default_factory=dict)
    tunnels: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # The vestibule and the dormitory always exist and hold the whole colony.
        for name in (VESTIBULE, DORMITORY):
            self.rooms.setdefault(name, Room(name, math.inf))

    # ------------------------------------------------------------------ #
    # Reading an anthill file
    # ------------------------------------------------------------------ #
    @classmethod
    def from_file(cls, path: str | Path) -> "Anthill":
        path = Path(path)
        anthill = cls(name=path.stem)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            anthill._read_line(line, number)
        return anthill

    def _read_line(self, line: str, number: int) -> None:
        match = _ANTS_PATTERN.match(line)
        if match is not None:
            self.ant_count = int(match.group(1))
            return

        # Tunnels are checked before rooms: "S1 - S2" also looks like a room name.
        match = _TUNNEL_PATTERN.match(line)
        if match is not None:
            self.add_tunnel(match.group(1), match.group(2))
            return

        match = _ROOM_PATTERN.match(line)
        if match is not None:
            capacity = int(match.group(2)) if match.group(2) else 1
            self.add_room(match.group(1), capacity)
            return

        raise ValueError(f"{self.name}: unreadable line {number} -> {line!r}")

    def add_room(self, name: str, capacity: float = 1) -> Room:
        # The vestibule and the dormitory keep their unlimited capacity.
        if name in (VESTIBULE, DORMITORY):
            capacity = math.inf
        room = self.rooms.get(name)
        if room is None:
            room = Room(name, capacity)
            self.rooms[name] = room
        else:
            room.capacity = capacity
        return room

    def add_tunnel(self, source: str, target: str) -> None:
        # A tunnel may mention a room that was never declared on its own line.
        for name in (source, target):
            if name not in self.rooms:
                self.add_room(name)
        if (source, target) in self.tunnels or (target, source) in self.tunnels:
            return
        self.tunnels.append((source, target))

    # ------------------------------------------------------------------ #
    # Graph view
    # ------------------------------------------------------------------ #
    def graph(self) -> nx.Graph:
        # Rooms become nodes carrying their capacity, tunnels become edges:
        # a tunnel can be walked through in both directions.
        graph = nx.Graph(name=self.name, ants=self.ant_count)
        for room in self.rooms.values():
            graph.add_node(room.name, capacity=room.capacity)
        graph.add_edges_from(self.tunnels)
        return graph

    def sorted_rooms(self) -> list[str]:
        return sorted(self.rooms, key=_sort_key)

    def adjacency_matrix(self):
        return nx.to_numpy_array(self.graph(), nodelist=self.sorted_rooms())

    def neighbours(self, name: str) -> list[str]:
        return sorted(self.graph().neighbors(name), key=_sort_key)

    def capacity(self, name: str) -> float:
        return self.rooms[name].capacity

    def shortest_path(self) -> list[str] | None:
        # Fewest tunnels between the vestibule and the dormitory, ignoring capacities.
        try:
            return nx.shortest_path(self.graph(), VESTIBULE, DORMITORY)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def layout(self) -> dict[str, tuple[float, float]]:
        # A room sits in the column matching its distance to the vestibule, so the
        # drawing reads from left (entrance) to right (dormitory).
        graph = self.graph()
        distances = nx.single_source_shortest_path_length(graph, VESTIBULE)
        depth = max(distances.values(), default=0)
        unreachable_column = depth + 1

        columns: dict[int, list[str]] = {}
        for room in self.sorted_rooms():
            columns.setdefault(distances.get(room, unreachable_column), []).append(room)

        # The dormitory always ends up alone in the last column: it is the finish line.
        dormitory_column = distances.get(DORMITORY, unreachable_column)
        last = max(columns)
        if dormitory_column != last or len(columns[last]) > 1:
            columns[dormitory_column].remove(DORMITORY)
            columns.setdefault(last + 1, []).append(DORMITORY)
            if not columns[dormitory_column]:
                del columns[dormitory_column]

        positions: dict[str, tuple[float, float]] = {}
        for column, rooms in columns.items():
            for rank, room in enumerate(rooms):
                y = (rank - (len(rooms) - 1) / 2) * ROW_SPACING
                positions[room] = (column * COLUMN_SPACING, y)
        return positions

    def figure_size(self, positions: dict[str, tuple[float, float]]) -> tuple[float, float]:
        xs = [x for x, _ in positions.values()]
        ys = [y for _, y in positions.values()]
        width = max(8.0, 1.3 * (max(xs) - min(xs) + 2))
        height = max(3.5, max(ys) - min(ys) + 2)
        return width, height

    def draw(self, image_path: str | Path | None = None, show: bool = False):
        graph = self.graph()
        positions = self.layout()
        sizes = [_node_size(name, graph.nodes[name]["capacity"]) for name in graph.nodes]

        figure, axes = plt.subplots(figsize=self.figure_size(positions))
        _draw_tunnels(graph, positions, axes, list(graph.edges), sizes, "#b08968", 1.6)

        # The shortest path shows the most direct way down to the dormitory.
        path = self.shortest_path()
        if path:
            _draw_tunnels(graph, positions, axes, list(zip(path, path[1:])), sizes,
                          "#c1440e", 3.0)

        colours = [_room_colour(name, graph.nodes[name]["capacity"]) for name in graph.nodes]
        labels = {name: _room_label(name, graph.nodes[name]["capacity"]) for name in graph.nodes}
        nx.draw_networkx_nodes(graph, positions, ax=axes, node_color=colours,
                               node_size=sizes, edgecolors="#4a3728", linewidths=1.5)
        nx.draw_networkx_labels(graph, positions, ax=axes, labels=labels,
                                font_size=9, font_weight="bold")

        title = (f"{self.name} - {self.ant_count} ants, "
                 f"{graph.number_of_nodes()} rooms, {graph.number_of_edges()} tunnels")
        if path:
            title += f"\nshortest path: {' - '.join(path)} ({len(path) - 1} tunnels)"
        else:
            title += "\nno path from the vestibule to the dormitory"
        axes.set_title(title, fontsize=11)
        axes.margins(0.12)
        axes.axis("off")
        figure.tight_layout()

        _finish(figure, image_path, show)
        return figure

    # ------------------------------------------------------------------ #
    def summary(self) -> str:
        rooms = ", ".join(str(self.rooms[name]) for name in self.sorted_rooms())
        lines = [
            f"Anthill \"{self.name}\"",
            f"  ants    : {self.ant_count}",
            f"  rooms   : {len(self.rooms)} -> {rooms}",
            f"  tunnels : {len(self.tunnels)}",
        ]
        path = self.shortest_path()
        if path:
            lines.append(f"  shortest path : {' - '.join(path)} ({len(path) - 1} tunnels)")
        else:
            lines.append("  shortest path : none (the dormitory cannot be reached)")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


@dataclass
class Move:
    ant: str
    source: str
    target: str

    def __str__(self) -> str:
        return f"{self.ant} - {self.source} - {self.target}"


@dataclass
class Solution:
    anthill: Anthill
    # One trajectory per ant: the room it stands in at every step, step 0 included.
    trajectories: dict[str, list[str]] = field(default_factory=dict)
    steps: list[list[Move]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.steps = self._build_steps()

    def _build_steps(self) -> list[list[Move]]:
        # A step holds every ant that changes room; waiting ants are not written down.
        steps = []
        for index in range(self.step_count):
            moves = [Move(ant, path[index], path[index + 1])
                     for ant, path in self.trajectories.items()
                     if path[index] != path[index + 1]]
            steps.append(moves)
        return steps

    @property
    def step_count(self) -> int:
        if not self.trajectories:
            return 0
        return len(next(iter(self.trajectories.values()))) - 1

    def occupants(self, step: int) -> dict[str, list[str]]:
        # Ants standing in each room at the beginning of the given step.
        rooms: dict[str, list[str]] = {name: [] for name in self.anthill.rooms}
        for ant, path in self.trajectories.items():
            rooms[path[step]].append(ant)
        return rooms

    def as_text(self) -> str:
        lines = []
        for index, moves in enumerate(self.steps, 1):
            lines.append(f"+++ E{index} +++")
            lines.extend(str(move) for move in moves)
        return "\n".join(lines)

    def errors(self) -> list[str]:
        # Independent check of the rules, run on the produced trajectories.
        problems = []
        graph = self.anthill.graph()

        for ant, path in self.trajectories.items():
            if path[0] != VESTIBULE:
                problems.append(f"{ant} does not start in the vestibule")
            if path[-1] != DORMITORY:
                problems.append(f"{ant} does not end in the dormitory")
            for index in range(len(path) - 1):
                source, target = path[index], path[index + 1]
                if source != target and not graph.has_edge(source, target):
                    problems.append(f"{ant} jumps from {source} to {target} with no tunnel")

        for index in range(self.step_count + 1):
            counts = Counter(path[index] for path in self.trajectories.values())
            for room, count in counts.items():
                capacity = self.anthill.capacity(room)
                if count > capacity:
                    problems.append(f"step {index}: {count} ants in {room} "
                                    f"which holds {int(capacity)}")
        return problems

    # ------------------------------------------------------------------ #
    # Step by step drawing
    # ------------------------------------------------------------------ #
    def draw_step(self, step: int, image_path: str | Path | None = None, show: bool = False):
        anthill = self.anthill
        graph = anthill.graph()
        positions = anthill.layout()
        occupants = self.occupants(step)
        sizes = [_node_size(name, graph.nodes[name]["capacity"]) for name in graph.nodes]

        figure, axes = plt.subplots(figsize=anthill.figure_size(positions))
        _draw_tunnels(graph, positions, axes, list(graph.edges), sizes, "#d6ccc2", 1.4)

        # Tunnels used by the step that is about to happen.
        moves = self.steps[step] if step < self.step_count else []
        if moves:
            used = {(move.source, move.target) for move in moves}
            _draw_tunnels(graph, positions, axes, sorted(used), sizes, "#c1440e", 2.6)

        colours = [_busy_colour(name, occupants[name]) for name in graph.nodes]
        labels = {name: _busy_label(name, graph.nodes[name]["capacity"], occupants[name])
                  for name in graph.nodes}
        nx.draw_networkx_nodes(graph, positions, ax=axes, node_color=colours,
                               node_size=sizes, edgecolors="#4a3728", linewidths=1.5)
        nx.draw_networkx_labels(graph, positions, ax=axes, labels=labels,
                                font_size=8, font_weight="bold")

        arrived = len(occupants[DORMITORY])
        title = (f"{anthill.name} - step {step}/{self.step_count}   "
                 f"dormitory: {arrived}/{anthill.ant_count} ants")
        if moves:
            title += f"\n+++ E{step + 1} +++  " + _move_digest(moves)
        else:
            title += "\nthe whole colony is asleep" if arrived else "\nbefore the first move"
        axes.set_title(title, fontsize=10)
        axes.margins(0.12)
        axes.axis("off")
        figure.tight_layout()

        _finish(figure, image_path, show)
        return figure

    def draw_steps(self, folder: str | Path, animation: bool = True) -> list[Path]:
        # One image per step, plus an animated version when Pillow is available.
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        frames = []
        for step in range(self.step_count + 1):
            image = folder / f"step_{step:02d}.png"
            self.draw_step(step, image_path=image)
            frames.append(image)
        if animation and frames:
            _write_animation(frames, folder / "animation.gif")
        return frames

    def summary(self) -> str:
        moves = sum(len(step) for step in self.steps)
        return (f"solved in {self.step_count} steps "
                f"({moves} moves for {self.anthill.ant_count} ants)")


# ---------------------------------------------------------------------- #
# Solver: fewest possible steps
# ---------------------------------------------------------------------- #
def solve(anthill: Anthill) -> Solution | None:
    # No dormitory in sight, or no ant to move: nothing to schedule.
    path = anthill.shortest_path()
    if path is None or anthill.ant_count <= 0:
        return None

    shortest = len(path) - 1
    # Worst case: ants queue up one behind the other along the shortest path.
    longest = shortest + anthill.ant_count - 1

    # Waiting longer can never hurt, so the feasible horizons form a range:
    # binary search for the first one that lets the whole colony arrive.
    low, high = shortest, longest
    while low < high:
        middle = (low + high) // 2
        if _max_arrivals(anthill, middle)[0] >= anthill.ant_count:
            high = middle
        else:
            low = middle + 1

    # The number of steps is settled: pick the cheapest schedule of that length.
    network = _time_expanded_network(anthill, low)
    flow = nx.max_flow_min_cost(network, _SOURCE, _SINK)
    trajectories = _extract_trajectories(anthill, low, flow)
    return Solution(anthill=anthill, trajectories=trajectories)


def _time_expanded_network(anthill: Anthill, horizon: int) -> nx.DiGraph:
    # Every room is copied once per step. A room is split in two nodes so the
    # edge between them can carry the capacity of the room at that very step,
    # which is exactly the rule "an ant enters a room only if there is space
    # for it once everybody has moved".
    colony = anthill.ant_count
    network = nx.DiGraph()

    for step in range(horizon + 1):
        for room in anthill.rooms.values():
            capacity = colony if room.is_unlimited else int(room.capacity)
            network.add_edge(("in", room.name, step), ("out", room.name, step),
                             capacity=capacity)

    for step in range(horizon):
        for name in anthill.rooms:
            # Waiting in the same room until the next step. Waiting anywhere but
            # in the dormitory costs one unit, so that among all the schedules
            # taking the same number of steps the solver picks the one where the
            # ants dawdle the least.
            network.add_edge(("out", name, step), ("in", name, step + 1),
                             capacity=colony, weight=0 if name == DORMITORY else 1)
        for first, second in anthill.tunnels:
            # Crossing a tunnel takes exactly one step. Ants never walk back into
            # the vestibule and never leave the dormitory: both moves can only
            # replace plain waiting, so dropping them keeps the optimum.
            for source, target in ((first, second), (second, first)):
                if target == VESTIBULE or source == DORMITORY:
                    continue
                network.add_edge(("out", source, step), ("in", target, step + 1),
                                 capacity=colony)

    network.add_edge(_SOURCE, ("in", VESTIBULE, 0), capacity=colony)
    network.add_edge(("out", DORMITORY, horizon), _SINK, capacity=colony)
    return network


def _max_arrivals(anthill: Anthill, horizon: int) -> tuple[int, dict]:
    # How many ants can reach the dormitory within that many steps?
    # Ants are interchangeable, so counting them is a maximum flow problem.
    network = _time_expanded_network(anthill, horizon)
    return nx.maximum_flow(network, _SOURCE, _SINK)


def _extract_trajectories(anthill: Anthill, horizon: int, flow: dict) -> dict[str, list[str]]:
    # Split the flow back into one unit per ant, each unit being a trajectory.
    remaining = {node: dict(targets) for node, targets in flow.items()}
    trajectories = []
    for _ in range(anthill.ant_count):
        rooms = []
        node = _SOURCE
        while node != _SINK:
            following = next(target for target, units in remaining[node].items() if units > 0)
            remaining[node][following] -= 1
            if following != _SINK and following[0] == "in":
                rooms.append(following[1])
            node = following
        trajectories.append(rooms)

    _undo_swaps(trajectories, horizon)
    # Number the ants in the order they leave the vestibule, which reads better.
    trajectories.sort(key=lambda rooms: (_departure(rooms), rooms))
    return {f"f{index}": rooms for index, rooms in enumerate(trajectories, 1)}


def _undo_swaps(trajectories: list[list[str]], horizon: int) -> None:
    # Two ants exchanging their rooms during the same step is allowed by the flow
    # but pointless: since ants are interchangeable, swapping what they do next
    # lets both of them stay where they are.
    for step in range(horizon):
        moves: dict[tuple[str, str], list[int]] = {}
        for index, rooms in enumerate(trajectories):
            source, target = rooms[step], rooms[step + 1]
            if source != target:
                moves.setdefault((source, target), []).append(index)
        for (source, target), ants in moves.items():
            opposite = moves.get((target, source))
            while ants and opposite:
                first, second = ants.pop(), opposite.pop()
                trajectories[first][step + 1:], trajectories[second][step + 1:] = (
                    trajectories[second][step + 1:], trajectories[first][step + 1:])


def _departure(rooms: list[str]) -> int:
    for step in range(len(rooms) - 1):
        if rooms[step] != rooms[step + 1]:
            return step
    return len(rooms)


# ---------------------------------------------------------------------- #
# Drawing helpers
# ---------------------------------------------------------------------- #
def _draw_tunnels(graph: nx.Graph, positions: dict, axes, edges: list, sizes: list,
                  colour: str, width: float) -> None:
    # Straight between neighbouring rooms, curved otherwise: a tunnel flying over
    # other rooms would be hidden right behind them if it were drawn straight.
    straight, curved = [], []
    for source, target in edges:
        columns = abs(positions[source][0] - positions[target][0]) / COLUMN_SPACING
        rows = abs(positions[source][1] - positions[target][1]) / ROW_SPACING
        neighbours = columns < 1.01 and (columns > 0.99 or rows < 1.01)
        (straight if neighbours else curved).append((source, target))

    if straight:
        nx.draw_networkx_edges(graph, positions, ax=axes, edgelist=straight,
                               edge_color=colour, width=width)
    if curved:
        nx.draw_networkx_edges(graph, positions, ax=axes, edgelist=curved, node_size=sizes,
                               edge_color=colour, width=width, arrows=True,
                               arrowstyle="-", connectionstyle="arc3,rad=0.22")


def _finish(figure, image_path, show: bool) -> None:
    if image_path is not None:
        image_path = Path(image_path)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(image_path, dpi=140)
    if show:
        plt.show()
    else:
        plt.close(figure)


def _sort_key(name: str) -> tuple[int, int, str]:
    # Sv first, then S1, S2, ... S10 in numeric order, and Sd last.
    if name == VESTIBULE:
        return (0, 0, name)
    if name == DORMITORY:
        return (2, 0, name)
    number = re.search(r"\d+", name)
    return (1, int(number.group()) if number else 0, name)


def _room_colour(name: str, capacity: float) -> str:
    if name == VESTIBULE:
        return "#8ecae6"   # the entrance, close to the surface
    if name == DORMITORY:
        return "#ffb703"   # where the colony is heading
    if capacity > 1:
        return "#a7c957"   # roomy enough for several ants
    return "#e9edc9"       # one ant at a time


def _busy_colour(name: str, occupants: list[str]) -> str:
    if name == VESTIBULE:
        return "#8ecae6"
    if name == DORMITORY:
        return "#ffb703"
    return "#e76f51" if occupants else "#f4f1de"


def _node_size(name: str, capacity: float) -> int:
    if name in (VESTIBULE, DORMITORY):
        return 2200
    return 800 + 200 * min(int(capacity), 6)


def _room_label(name: str, capacity: float) -> str:
    if capacity == math.inf or capacity <= 1:
        return name
    return f"{name}\n({int(capacity)})"


def _busy_label(name: str, capacity: float, occupants: list[str]) -> str:
    if not occupants:
        return _room_label(name, capacity)
    if len(occupants) <= 2 and capacity != math.inf:
        return f"{name}\n{' '.join(occupants)}"
    return f"{name}\n{len(occupants)} ants"


def _move_digest(moves: list[Move], limit: int = 5) -> str:
    shown = "   ".join(str(move) for move in moves[:limit])
    if len(moves) > limit:
        shown += f"   (+{len(moves) - limit} more)"
    return shown


def _write_animation(frames: list[Path], target: Path) -> Path | None:
    # Pillow ships with matplotlib in most setups; skip the gif when it does not.
    try:
        from PIL import Image
    except ImportError:
        return None
    images = [Image.open(frame).convert("P", palette=Image.ADAPTIVE) for frame in frames]
    images[0].save(target, save_all=True, append_images=images[1:],
                   duration=900, loop=0)
    return target


def load_anthills(folder: str | Path = "fourmilieres") -> list[Anthill]:
    return [Anthill.from_file(path) for path in sorted(Path(folder).glob("*.txt"))]
