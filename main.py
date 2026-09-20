# Une vie de fourmi : solve every anthill and produce the three required outputs:
# the graph of the anthill, the list of steps, and one picture per step.
#
#   python main.py                                   all anthills
#   python main.py fourmilieres/fourmiliere_un.txt   a single anthill
#   python main.py --quiet                           recap only, no step listing
#   python main.py --no-frames                       skip the step by step pictures

import argparse
import sys
from pathlib import Path

from ants import Anthill, load_anthills, solve

ANTHILL_FOLDER = Path("fourmilieres")
OUTPUT_FOLDER = Path("graphes")

# The Windows console is not UTF-8 by default and would choke on the output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move every ant to the dormitory.")
    parser.add_argument("files", nargs="*", type=Path,
                        help=f"anthill files (default: everything in {ANTHILL_FOLDER}/)")
    parser.add_argument("--output", type=Path, default=OUTPUT_FOLDER,
                        help=f"folder for the pictures (default: {OUTPUT_FOLDER}/)")
    parser.add_argument("--quiet", action="store_true",
                        help="print the recap only, without the list of steps")
    parser.add_argument("--no-frames", action="store_true",
                        help="do not draw one picture per step")
    parser.add_argument("--show", action="store_true",
                        help="open the graph of each anthill in a window")
    return parser.parse_args()


def run(anthill: Anthill, arguments: argparse.Namespace) -> bool:
    print(anthill.summary())

    # 1. the anthill as a graph
    graph_image = arguments.output / f"{anthill.name}.png"
    anthill.draw(image_path=graph_image, show=arguments.show)
    print(f"  graph   : {graph_image}")

    solution = solve(anthill)
    if solution is None:
        print("  no solution: the ants cannot reach the dormitory\n")
        return False

    # 2. every step needed to move the ants
    print(f"  {solution.summary()}")
    mistakes = solution.errors()
    print(f"  rules   : {'respected' if not mistakes else mistakes}")

    steps_file = arguments.output / anthill.name / "steps.txt"
    steps_file.parent.mkdir(parents=True, exist_ok=True)
    steps_file.write_text(solution.as_text() + "\n", encoding="utf-8")
    print(f"  steps   : {steps_file}")

    # 3. the ants moving inside the anthill, step by step
    if not arguments.no_frames:
        frames = solution.draw_steps(arguments.output / anthill.name)
        print(f"  frames  : {len(frames)} pictures in {frames[0].parent}")

    if not arguments.quiet:
        print()
        print(solution.as_text())
    print()
    return not mistakes


def main() -> None:
    arguments = read_arguments()
    anthills = ([Anthill.from_file(path) for path in arguments.files]
                if arguments.files else load_anthills(ANTHILL_FOLDER))

    if not anthills:
        print(f"no anthill found in {ANTHILL_FOLDER}/")
        return

    solved = sum(run(anthill, arguments) for anthill in anthills)
    print(f"{solved}/{len(anthills)} anthills solved, pictures in {arguments.output}/")


if __name__ == "__main__":
    main()
