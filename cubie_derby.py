from collections import defaultdict
import random
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import IntEnum

"""
CONSTANTS
"""
DEBUG = 1

COURSE_LENGTH = 30
DIE_MIN = 1
DIE_MAX = 6

THRUSTERS = [2, 10, 15, 22]
BLOCKERS = [9, 27]
TELEPORTERS = [5, 19]

class Direction(IntEnum):
    FORWARD = 1
    BACKWARD = -1


class Cube(ABC):
    def __init__(self, name: str, position: int = 0):
        self.name = name
        self.position = position

    @abstractmethod
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

"""
Cubes

Luuk: Thruster +2 extra pads forward, Block +1 extra pad back

Sigrika: Up to 2 cubes right ahead of this one move 1 fewer pad this turn. Determined by turn order.
         Cannot freeze Cubes in place or make them move backwards.

Denia: If num rolled matches previous roll, advance 2 extra pads.

Hiyuki: Encountering Abbowser makes this advance 1 extra pad each turn afterward.

Carte: If last after own action, 60% chance to move 2 extra pads in all turns afterward.

Phoebe: 50% chance to move an extra pad.

Abbowser: Starting from turn 3, start moving from finish line to starting line. Affected by all
          course mechanisms. Rolls 1-6. Always bottom of stack. IF separated from all other cubes
          at end of each turn, teleport back to finish line.
"""
class Luuk(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position_luuk(
            game,
            self.position,
            roll(),
            direction
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)

class Sigrika(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position(
            game,
            self.position,
            roll(),
            direction
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)


class Denia(Cube):
    def __init__(self, name: str, position: int = 0):
        self.name = name
        self.position = position
        self.prev_roll = None

    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        current_roll = roll()

        if self.prev_roll == current_roll:
            self.prev_roll = current_roll
            current_roll += 2
        else:
            self.prev_roll = current_roll

        next_position = get_next_position(
            game,
            self.position,
            current_roll,
            direction,
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)


class Hiyuki(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position(
            game,
            self.position,
            roll() + (1 if game.hiyuki_buff else 0),
            direction,
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)


class Carte(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position(
            game,
            self.position,
            roll() + (2 if game.carte_buff and random.random() < 0.6 else 0),
            direction,
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)


class Phoebe(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position(
            game,
            self.position,
            roll() + (1 if random.random() < 0.5 else 0),
            direction,
        )
        from_stack = game.course[self.position]
        to_stack = game.course[next_position]
        game._move(from_stack, to_stack, self)


class Abbowser(Cube):
    def move(self, game: 'Game', direction: Direction = Direction.FORWARD):
        next_position = get_next_position(
            game,
            self.position,
            roll(),
            direction,
        )

        collect_cubes = []
        for i in range(self.position, next_position + direction, direction):
            if not game.hiyuki_buff and any(isinstance(cube, Hiyuki) for cube in game.course[i].cubes):
                game.hiyuki_buff = True

            if i != self.position and not game.abbowser_return and len(game.course[i].cubes):
                game.abbowser_return = True

            collect_cubes.extend(game.course[i].cubes)
            game.course[i].cubes.clear()

        game.course[next_position].cubes = collect_cubes
        for cube in game.course[next_position].cubes:
            cube.position = next_position

        # Abbowser always on bottom
        abbowser = next(cube for cube in game.course[self.position].cubes if cube.name == "Abbowser")
        game.course[self.position].cubes.remove(abbowser)
        game.course[self.position].cubes.insert(0, abbowser)
        print(f"Abbowser moved to position {next_position}")
        print(f"Stack after Abbowser moved: {game.course[self.position]}")

        # If only Abbowser on ending square, teleport back to stage end
        if len(game.course[next_position].cubes) == 1 and game.abbowser_return:
            assert self in game.course[self.position].cubes, "Something went horribly wrong"
            print(f"Abbowser returned to position {COURSE_LENGTH - 1}")
            if self in game.course[self.position].cubes:
                game.course[self.position].cubes.remove(self)
            game.course[COURSE_LENGTH - 1].cubes.append(self)
            self.position = COURSE_LENGTH - 1

"""
Environment

Positions
0 ... 29

Thruster - End move on this pad = propel to next pad
[2, 10, 15, 22]

Blocker - End move on this pad = propel to previous pad
[9, 27]

Teleporter - End move on this pad = randomize stack order
[5, 19]
"""
@dataclass
class Stack:
    cubes: list['Cube']
    position: int

    def __repr__(self):
        return str(self.cubes)


class Game:
    def __init__(self) -> None:
        self.current_turn = 0
        self.cubes: list[Cube] = [
            Luuk("Luuk"),
            Sigrika("Sigrika"),
            Denia("Denia"),
            Hiyuki("Hiyuki"),
            Carte("Carte"),
            Phoebe("Phoebe"),
            Abbowser("Abbowser", COURSE_LENGTH - 1),
        ]

        self.course = [Stack(cubes=[], position=i) for i in range(COURSE_LENGTH)]
        abbowser = next(cube for cube in self.cubes if cube.name == "Abbowser")
        self.course[0].cubes.extend([cube for cube in self.cubes if cube != abbowser])
        self.course[COURSE_LENGTH - 1].cubes.append(abbowser)


        # Buffs / Debuffs
        self.sigrika_debuff = 0
        self.hiyuki_buff = False
        self.carte_buff = False
        self.abbowser_return = False


    def play_turn(self):
        print_header(f"Start of turn {self.current_turn}")
        turn_order = list(range(len(self.cubes)))
        random.shuffle(turn_order)

        for i in turn_order:
            cube = self.cubes[i]
            print(f"Start of {cube.name}'s turn")

            if isinstance(cube, Abbowser):
                if self.current_turn >= 2:
                    cube.move(self, Direction.BACKWARD)
                continue

            if isinstance(cube, Sigrika):
                cube.move(self, Direction.FORWARD)
                debug_log("Sigrika Debuff Activated")
                self.sigrika_debuff = 2
            else:
                cube.move(self, Direction.FORWARD)

        if isinstance(self.cubes[turn_order[-1]], Carte):
            self.carte_buff = True

        debug_log("Sigrika Debuff Deactivated")
        self.sigrika_debuff = 0
        self.current_turn += 1


    def start_game(self):
        print_header("Welcome to Cubie Derby")
        while not self._is_game_over():
            self.play_turn()

        winners = self._get_winners()
        print_header("Cubie Derby Results")
        print("------ Winners ------")
        for winner in winners:
            print(winner.name)
        print("------ Cube Locations ------")
        for cube in sorted(self.cubes, key=lambda c: c.position, reverse=True):
            print(f"{cube.name} - {cube.position}")

        self.winner = winners[0]


    def run_trials(self, n: int) -> None:
        results = defaultdict(int)

        for _ in range(n):
            game_instance = Game()
            game_instance.start_game()
            results[game_instance.winner.name] += 1

        print("=" * 60)
        print(f"Results from {n} Games:")
        print("=" * 60)
        results = sorted(results.items(), key=lambda k: k[1], reverse=True)
        for k, v in results:
            print(f"{k}: {v}")



    def _is_game_over(self) -> bool:
        return any(cube.position >= COURSE_LENGTH - 1 for cube in self.cubes if cube.name != "Abbowser")


    def _get_winners(self) -> list[Cube]:
        return list(reversed([cube for cube in self.course[COURSE_LENGTH - 1].cubes if cube.name != "Abbowser"]))


    def _move(self, from_stack: Stack, to_stack: Stack, cube: Cube) -> None:
        if to_stack.position == from_stack.position:
            return

        if self.current_turn == 0:
            self._move_cube(from_stack, to_stack, cube)
        else:
            self._move_stack(from_stack, to_stack, cube)


    def _move_stack(self, from_stack: Stack, to_stack: Stack, cube: Cube) -> None:
        cube_idx = from_stack.cubes.index(cube)
        to_move = from_stack.cubes[cube_idx:]

        for cube in to_move:
            print(f"{cube.name} moved to position {to_stack.position}")
            cube.position = to_stack.position
            to_stack.cubes.append(cube)
            from_stack.cubes.remove(cube)

        if to_stack.position in TELEPORTERS:
            random.shuffle(to_stack.cubes)

        print(to_stack)


    def _move_cube(self, from_stack: Stack, to_stack: Stack, cube: Cube) -> None:
        cube.position = to_stack.position
        to_stack.cubes.append(cube)
        from_stack.cubes.remove(cube)
        print(f"{cube.name} moved to position {to_stack.position}: {to_stack}")


"""
HELPERS
"""
def roll(min: int = DIE_MIN, max: int = DIE_MAX) -> int:
    return random.randint(min, max)


def get_next_position(game: 'Game', start: int, roll: int, direction: Direction = Direction.FORWARD) -> int:
    if game.sigrika_debuff > 0:
        debug_log("Sigrika Debuff Applied")
        game.sigrika_debuff -= 1
        roll = max(1, roll - 1)

    next_position = start + (roll * direction)

    if next_position <= 0:
        return 0
    elif next_position >= COURSE_LENGTH - 1:
        return COURSE_LENGTH - 1
    elif next_position in THRUSTERS:
        return get_next_position(game, next_position, 1)
    elif next_position in BLOCKERS:
        return get_next_position(game, next_position, 1, Direction.BACKWARD)
    else:
        return next_position


def get_next_position_luuk(game: 'Game', start: int, roll: int, direction: Direction = Direction.FORWARD) -> int:
    if game.sigrika_debuff > 0:
        game.sigrika_debuff -= 1
        roll = max(0, roll - 1)

    next_position = start + (roll * direction)

    if next_position <= 0:
        return 0
    elif next_position >= COURSE_LENGTH - 1:
        return COURSE_LENGTH - 1
    elif next_position in THRUSTERS:
        return get_next_position(game, next_position, 3)
    elif next_position in BLOCKERS:
        return get_next_position(game, next_position, 2, Direction.BACKWARD)
    else:
        return next_position


def debug_log(message: str) -> None:
    if DEBUG:
        print(f"\033[31m[DEBUG]\033[0m {message}")


def print_header(message: str) -> None:
    print(f"============ {message} ============")

game_instance = Game()
# game_instance.start_game()
game_instance.run_trials(100000)