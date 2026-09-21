# Une vie de fourmi : anthill model, optimal scheduling and drawing.
#
# The whole exercise is: a colony of ants starts in the vestibule (Sv) and must
# reach the dormitory (Sd) in as few steps as possible. During one step every
# ant may either stay where it is or walk through exactly one tunnel, and a room
# never holds more ants than its capacity.
#
# This module is built in three layers:
#   1. Anthill  -> reads a .txt file, stores the rooms/tunnels, draws the map.
#   2. Solution -> a schedule (one trajectory per ant), its text output and its
#                  step by step pictures.
#   3. solve()  -> turns an Anthill into an optimal Solution using a max flow /
#                  min cost computation on a "time expanded" network.
#
# Anthill file format:
# f=5         -> number of ants in the colony
# S1          -> a room holding a single ant
# S2 { 4 }    -> a room holding 4 ants at the same time
# Sv - S1     -> a tunnel between the vestibule and room 1

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

# The two rooms that always exist: the entrance and the finish line.
VESTIBULE = "Sv"
DORMITORY = "Sd"

# Room spacing on the drawings: one column is one step away from the vestibule.
COLUMN_SPACING = 1.6
ROW_SPACING = 1.2

# Regular expressions used to read one line of an anthill file.
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
    # One room of the anthill: a name and how many ants fit in it at once.
    #
    # The vestibule and the dormitory use ``math.inf`` because they hold the whole
    # colony; every other room holds a single ant unless the file says otherwise.

    name: str
    capacity: float = 1

    @property
    def is_unlimited(self) -> bool:
        # True for the vestibule and the dormitory, which never overflow.
        return self.capacity == math.inf

    def __str__(self) -> str:
        # Render the room the way the anthill files write it: ``S2{4}``.
        if self.is_unlimited:
            return self.name
        return f"{self.name}{{{int(self.capacity)}}}"


@dataclass
class Anthill:
    # The map of one anthill: its ants, its rooms and the tunnels between them.

    name: str = "anthill"
    ant_count: int = 0
    rooms: dict[str, Room] = field(default_factory=dict)
    tunnels: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Guarantee the two special rooms exist even if the file never names them.
        # The vestibule and the dormitory always exist and hold the whole colony.
        for name in (VESTIBULE, DORMITORY):
            self.rooms.setdefault(name, Room(name, math.inf))

    # ------------------------------------------------------------------ #
    # Reading an anthill file
    # ------------------------------------------------------------------ #
    @classmethod
    def from_file(cls, path: str | Path) -> "Anthill":
        # Build an Anthill from a ``.txt`` file, one instruction per line.
        #
        # Blank lines and ``#`` comments are skipped; the file name (without its
        # extension) becomes the name of the anthill.
        path = Path(path)
        anthill = cls(name=path.stem)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            anthill._read_line(line, number)
        return anthill

    def _read_line(self, line: str, number: int) -> None:
        # Interpret a single line: ant count, tunnel or room.
        #
        # The line number is only carried around to report a useful error message
        # when nothing matches.
        # "f=5": how many ants wait in the vestibule at step 0.
        match = _ANTS_PATTERN.match(line)
        if match is not None:
            self.ant_count = int(match.group(1))
            return

        # Tunnels are checked before rooms: "S1 - S2" also looks like a room name.
        match = _TUNNEL_PATTERN.match(line)
        if match is not None:
            self.add_tunnel(match.group(1), match.group(2))
            return

        # "S2 { 4 }" or plain "S2": a room, with capacity 1 when none is given.
        match = _ROOM_PATTERN.match(line)
        if match is not None:
            capacity = int(match.group(2)) if match.group(2) else 1
            self.add_room(match.group(1), capacity)
            return

        raise ValueError(f"{self.name}: unreadable line {number} -> {line!r}")

    def add_room(self, name: str, capacity: float = 1) -> Room:
        # Create the room, or update the capacity of a room already known.
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
        # Register a two way tunnel, ignoring a tunnel that is already known.
        # A tunnel may mention a room that was never declared on its own line.
        for name in (source, target):
            if name not in self.rooms:
                self.add_room(name)
        # A tunnel has no direction, so "S1 - S2" and "S2 - S1" are the same one.
        if (source, target) in self.tunnels or (target, source) in self.tunnels:
            return
        self.tunnels.append((source, target))

    # ------------------------------------------------------------------ #
    # Graph view
    # ------------------------------------------------------------------ #
    def graph(self) -> nx.Graph:
        # Return the anthill as an undirected networkx graph.
        # Rooms become nodes carrying their capacity, tunnels become edges:
        # a tunnel can be walked through in both directions.
        graph = nx.Graph(name=self.name, ants=self.ant_count)
        for room in self.rooms.values():
            graph.add_node(room.name, capacity=room.capacity)
        graph.add_edges_from(self.tunnels)
        return graph

    def sorted_rooms(self) -> list[str]:
        # Room names in reading order: Sv first, then S1, S2, ... and Sd last.
        return sorted(self.rooms, key=_sort_key)

    def adjacency_matrix(self):
        # The adjacency matrix of the anthill, rows/columns in reading order.
        return nx.to_numpy_array(self.graph(), nodelist=self.sorted_rooms())

    def neighbours(self, name: str) -> list[str]:
        # The rooms reachable from ``name`` through a single tunnel.
        return sorted(self.graph().neighbors(name), key=_sort_key)

    def capacity(self, name: str) -> float:
        # How many ants the given room holds at the same time.
        return self.rooms[name].capacity

    def shortest_path(self) -> list[str] | None:
        # The shortest route Sv -> Sd, or None when the dormitory is cut off.
        # Fewest tunnels between the vestibule and the dormitory, ignoring capacities.
        try:
            return nx.shortest_path(self.graph(), VESTIBULE, DORMITORY)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def layout(self) -> dict[str, tuple[float, float]]:
        # Compute the (x, y) position of every room used by all the drawings.
        # A room sits in the column matching its distance to the vestibule, so the
        # drawing reads from left (entrance) to right (dormitory).
        graph = self.graph()
        distances = nx.single_source_shortest_path_length(graph, VESTIBULE)
        depth = max(distances.values(), default=0)
        # Rooms no tunnel connects to the vestibule are parked one column further.
        unreachable_column = depth + 1

        # Group the rooms by column, keeping the reading order inside a column.
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

        # Inside a column the rooms are stacked vertically and centred on y = 0.
        positions: dict[str, tuple[float, float]] = {}
        for column, rooms in columns.items():
            for rank, room in enumerate(rooms):
                y = (rank - (len(rooms) - 1) / 2) * ROW_SPACING
                positions[room] = (column * COLUMN_SPACING, y)
        return positions

    def figure_size(self, positions: dict[str, tuple[float, float]]) -> tuple[float, float]:
        # Pick a figure size large enough for how far the rooms spread out.
        xs = [x for x, _ in positions.values()]
        ys = [y for _, y in positions.values()]
        width = max(8.0, 1.3 * (max(xs) - min(xs) + 2))
        height = max(3.5, max(ys) - min(ys) + 2)
        return width, height

    def draw(self, image_path: str | Path | None = None, show: bool = False):
        # Draw the map of the anthill and highlight its shortest path.
        #
        # Saves the picture to ``image_path`` when one is given, and/or opens a
        # window when ``show`` is true. Returns the matplotlib figure.
        graph = self.graph()
        positions = self.layout()
        sizes = [_node_size(name, graph.nodes[name]["capacity"]) for name in graph.nodes]

        # First layer: every tunnel, in a discreet earth colour.
        figure, axes = plt.subplots(figsize=self.figure_size(positions))
        _draw_tunnels(graph, positions, axes, list(graph.edges), sizes, "#b08968", 1.6)

        # The shortest path shows the most direct way down to the dormitory.
        path = self.shortest_path()
        if path:
            _draw_tunnels(graph, positions, axes, list(zip(path, path[1:])), sizes,
                          "#c1440e", 3.0)

        # Second layer: the rooms themselves, coloured and labelled by capacity.
        colours = [_room_colour(name, graph.nodes[name]["capacity"]) for name in graph.nodes]
        labels = {name: _room_label(name, graph.nodes[name]["capacity"]) for name in graph.nodes}
        nx.draw_networkx_nodes(graph, positions, ax=axes, node_color=colours,
                               node_size=sizes, edgecolors="#4a3728", linewidths=1.5)
        nx.draw_networkx_labels(graph, positions, ax=axes, labels=labels,
                                font_size=9, font_weight="bold")

        # The title recaps the size of the anthill and the shortest path found.
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
        # A short readable recap of the anthill, the one printed by main.py.
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
    # One ant walking through one tunnel during one step.

    ant: str
    source: str
    target: str

    def __str__(self) -> str:
        # The format required by the exercise: ``f1 - Sv - S1``.
        return f"{self.ant} - {self.source} - {self.target}"


@dataclass
class Solution:
    # A complete schedule: where every ant stands at every step.

    anthill: Anthill
    # One trajectory per ant: the room it stands in at every step, step 0 included.
    trajectories: dict[str, list[str]] = field(default_factory=dict)
    steps: list[list[Move]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # Derive the list of moves of each step from the trajectories.
        self.steps = self._build_steps()

    def _build_steps(self) -> list[list[Move]]:
        # Compare each pair of consecutive rooms to find out who moves when.
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
        # How many steps the colony needs (a trajectory holds one room more).
        if not self.trajectories:
            return 0
        return len(next(iter(self.trajectories.values()))) - 1

    def occupants(self, step: int) -> dict[str, list[str]]:
        # Which ants stand in which room at the beginning of ``step``.
        # Ants standing in each room at the beginning of the given step.
        rooms: dict[str, list[str]] = {name: [] for name in self.anthill.rooms}
        for ant, path in self.trajectories.items():
            rooms[path[step]].append(ant)
        return rooms

    def as_text(self) -> str:
        # The answer in the expected format: ``+++ E1 +++`` then one line per move.
        lines = []
        for index, moves in enumerate(self.steps, 1):
            lines.append(f"+++ E{index} +++")
            lines.extend(str(move) for move in moves)
        return "\n".join(lines)

    def errors(self) -> list[str]:
        # Re-check the rules on the produced schedule; an empty list means valid.
        # Independent check of the rules, run on the produced trajectories.
        problems = []
        graph = self.anthill.graph()

        # Rule 1: start in Sv, end in Sd, and only ever cross tunnels that exist.
        for ant, path in self.trajectories.items():
            if path[0] != VESTIBULE:
                problems.append(f"{ant} does not start in the vestibule")
            if path[-1] != DORMITORY:
                problems.append(f"{ant} does not end in the dormitory")
            for index in range(len(path) - 1):
                source, target = path[index], path[index + 1]
                if source != target and not graph.has_edge(source, target):
                    problems.append(f"{ant} jumps from {source} to {target} with no tunnel")

        # Rule 2: at every single step, no room holds more ants than its capacity.
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
        # Draw the anthill as it looks at the beginning of ``step``.
        #
        # Occupied rooms are coloured, the tunnels about to be used are highlighted
        # and the title recaps the moves of that step.
        anthill = self.anthill
        graph = anthill.graph()
        positions = anthill.layout()
        occupants = self.occupants(step)
        sizes = [_node_size(name, graph.nodes[name]["capacity"]) for name in graph.nodes]

        # Background layer: all the tunnels, very pale.
        figure, axes = plt.subplots(figsize=anthill.figure_size(positions))
        _draw_tunnels(graph, positions, axes, list(graph.edges), sizes, "#d6ccc2", 1.4)

        # Tunnels used by the step that is about to happen.
        moves = self.steps[step] if step < self.step_count else []
        if moves:
            used = {(move.source, move.target) for move in moves}
            _draw_tunnels(graph, positions, axes, sorted(used), sizes, "#c1440e", 2.6)

        # The rooms: red as soon as ants are inside, and labelled with who is there.
        colours = [_busy_colour(name, occupants[name]) for name in graph.nodes]
        labels = {name: _busy_label(name, graph.nodes[name]["capacity"], occupants[name])
                  for name in graph.nodes}
        nx.draw_networkx_nodes(graph, positions, ax=axes, node_color=colours,
                               node_size=sizes, edgecolors="#4a3728", linewidths=1.5)
        nx.draw_networkx_labels(graph, positions, ax=axes, labels=labels,
                                font_size=8, font_weight="bold")

        # The title tracks the progress of the colony towards the dormitory.
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
        # Save every step as a picture and return the list of files written.
        # One image per step, plus an animated version when Pillow is available.
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        frames = []
        # step_count + 1 pictures: the starting position counts as step 0.
        for step in range(self.step_count + 1):
            image = folder / f"step_{step:02d}.png"
            self.draw_step(step, image_path=image)
            frames.append(image)
        if animation and frames:
            _write_animation(frames, folder / "animation.gif")
        return frames

    def summary(self) -> str:
        # One line recap: number of steps and total number of moves.
        moves = sum(len(step) for step in self.steps)
        return (f"solved in {self.step_count} steps "
                f"({moves} moves for {self.anthill.ant_count} ants)")


# ---------------------------------------------------------------------- #
# Solver: fewest possible steps
# ---------------------------------------------------------------------- #
def solve(anthill: Anthill) -> Solution | None:
    # Find a schedule moving the whole colony to the dormitory in fewest steps.
    #
    # The method has three stages:
    #   1. bound the answer between the length of the shortest path and the worst
    #      case where the ants queue up one behind the other;
    #   2. binary search the smallest number of steps for which a maximum flow
    #      says the whole colony can arrive;
    #   3. recompute that flow at minimum cost to get a tidy schedule, then split
    #      the flow back into one trajectory per ant.
    #
    # Returns None when the dormitory is unreachable or there is no ant to move.
    # No dormitory in sight, or no ant to move: nothing to schedule.
    path = anthill.shortest_path()
    if path is None or anthill.ant_count <= 0:
        return None

    # Best case: a single ant walks straight down the shortest path.
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
    # Build the flow network modelling ``horizon`` steps of life in the anthill.
    #
    # One unit of flow is one ant, and a path from the source to the sink is the
    # trajectory of that ant through both the rooms and the steps.
    # Every room is copied once per step. A room is split in two nodes so the
    # edge between them can carry the capacity of the room at that very step,
    # which is exactly the rule "an ant enters a room only if there is space
    # for it once everybody has moved".
    colony = anthill.ant_count
    network = nx.DiGraph()

    # ("in", room, step) -> ("out", room, step): the capacity of the room itself.
    for step in range(horizon + 1):
        for room in anthill.rooms.values():
            capacity = colony if room.is_unlimited else int(room.capacity)
            network.add_edge(("in", room.name, step), ("out", room.name, step),
                             capacity=capacity)

    # Edges going from one step to the next: an ant either waits or crosses one tunnel.
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

    # The colony enters through the vestibule at step 0 and is counted in the
    # dormitory at the last step.
    network.add_edge(_SOURCE, ("in", VESTIBULE, 0), capacity=colony)
    network.add_edge(("out", DORMITORY, horizon), _SINK, capacity=colony)
    return network


def _max_arrivals(anthill: Anthill, horizon: int) -> tuple[int, dict]:
    # Return (ants able to arrive within ``horizon`` steps, the flow itself).
    # How many ants can reach the dormitory within that many steps?
    # Ants are interchangeable, so counting them is a maximum flow problem.
    network = _time_expanded_network(anthill, horizon)
    return nx.maximum_flow(network, _SOURCE, _SINK)


def _extract_trajectories(anthill: Anthill, horizon: int, flow: dict) -> dict[str, list[str]]:
    # Turn the computed flow into one named trajectory per ant.
    # Split the flow back into one unit per ant, each unit being a trajectory.
    remaining = {node: dict(targets) for node, targets in flow.items()}
    trajectories = []
    for _ in range(anthill.ant_count):
        # Walk the network from the source to the sink, consuming one unit of
        # flow on every edge taken, and note the room behind each "in" node.
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
    # Remove the pointless room exchanges, editing the trajectories in place.
    # Two ants exchanging their rooms during the same step is allowed by the flow
    # but pointless: since ants are interchangeable, swapping what they do next
    # lets both of them stay where they are.
    for step in range(horizon):
        # Group the ants moving during this step by the tunnel they take.
        moves: dict[tuple[str, str], list[int]] = {}
        for index, rooms in enumerate(trajectories):
            source, target = rooms[step], rooms[step + 1]
            if source != target:
                moves.setdefault((source, target), []).append(index)
        # Pair every move with a move going the other way, then exchange the ends
        # of the two trajectories: both ants now simply stay where they are.
        for (source, target), ants in moves.items():
            opposite = moves.get((target, source))
            while ants and opposite:
                first, second = ants.pop(), opposite.pop()
                trajectories[first][step + 1:], trajectories[second][step + 1:] = (
                    trajectories[second][step + 1:], trajectories[first][step + 1:])


def _departure(rooms: list[str]) -> int:
    # The step at which a trajectory first moves, used to number the ants.
    for step in range(len(rooms) - 1):
        if rooms[step] != rooms[step + 1]:
            return step
    # An ant that never moves is sorted last.
    return len(rooms)


# ---------------------------------------------------------------------- #
# Drawing helpers
# ---------------------------------------------------------------------- #
def _draw_tunnels(graph: nx.Graph, positions: dict, axes, edges: list, sizes: list,
                  colour: str, width: float) -> None:
    # Draw the given tunnels, bending the ones that fly over other rooms.
    # Straight between neighbouring rooms, curved otherwise: a tunnel flying over
    # other rooms would be hidden right behind them if it were drawn straight.
    straight, curved = [], []
    for source, target in edges:
        # Distance between the two rooms, counted in columns and rows of the layout.
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
    # Save and/or show a figure, then close it so matplotlib does not pile them up.
    if image_path is not None:
        image_path = Path(image_path)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(image_path, dpi=140)
    if show:
        plt.show()
    else:
        plt.close(figure)


def _sort_key(name: str) -> tuple[int, int, str]:
    # Sorting key putting the rooms in the order a human would read them.
    # Sv first, then S1, S2, ... S10 in numeric order, and Sd last.
    if name == VESTIBULE:
        return (0, 0, name)
    if name == DORMITORY:
        return (2, 0, name)
    number = re.search(r"\d+", name)
    return (1, int(number.group()) if number else 0, name)


def _room_colour(name: str, capacity: float) -> str:
    # Colour of a room on the map of the anthill.
    if name == VESTIBULE:
        return "#8ecae6"   # the entrance, close to the surface
    if name == DORMITORY:
        return "#ffb703"   # where the colony is heading
    if capacity > 1:
        return "#a7c957"   # roomy enough for several ants
    return "#e9edc9"       # one ant at a time


def _busy_colour(name: str, occupants: list[str]) -> str:
    # Colour of a room on a step picture: red as soon as an ant is inside.
    if name == VESTIBULE:
        return "#8ecae6"
    if name == DORMITORY:
        return "#ffb703"
    return "#e76f51" if occupants else "#f4f1de"


def _node_size(name: str, capacity: float) -> int:
    # Bigger circles for the two special rooms, and for the roomy ones.
    if name in (VESTIBULE, DORMITORY):
        return 2200
    return 800 + 200 * min(int(capacity), 6)


def _room_label(name: str, capacity: float) -> str:
    # Label of a room on the map: its name, plus its capacity when above one.
    if capacity == math.inf or capacity <= 1:
        return name
    return f"{name}\n({int(capacity)})"


def _busy_label(name: str, capacity: float, occupants: list[str]) -> str:
    # Label of a room on a step picture: the ants inside, or just how many.
    if not occupants:
        return _room_label(name, capacity)
    if len(occupants) <= 2 and capacity != math.inf:
        return f"{name}\n{' '.join(occupants)}"
    return f"{name}\n{len(occupants)} ants"


def _move_digest(moves: list[Move], limit: int = 5) -> str:
    # Shorten the moves of a step so that they fit in the title of a picture.
    shown = "   ".join(str(move) for move in moves[:limit])
    if len(moves) > limit:
        shown += f"   (+{len(moves) - limit} more)"
    return shown


def _write_animation(frames: list[Path], target: Path) -> Path | None:
    # Stitch the step pictures into an animated gif; returns None without Pillow.
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
    # Read every ``.txt`` anthill of a folder, in alphabetical order.
    return [Anthill.from_file(path) for path in sorted(Path(folder).glob("*.txt"))]
