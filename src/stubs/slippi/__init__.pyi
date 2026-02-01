"""Type stubs for py-slippi library."""

from datetime import datetime
from typing import BinaryIO, Optional, Sequence, Tuple, Union
import os
from .id import CSSCharacter, InGameCharacter, Stage, ActionState, Item as ItemType

class Game:
    start: Optional[Start]
    frames: list[Frame]
    end: Optional[End]
    metadata: Optional[Metadata]
    metadata_raw: Optional[dict[str, object]]

    def __init__(self, input: Union[BinaryIO, str, os.PathLike[str]]) -> None: ...

class Metadata:
    date: Optional[datetime]
    duration: Optional[int]
    platform: Optional[str]
    players: Optional[Tuple[Optional[Metadata.Player], ...]]

    class Player:
        characters: Optional[dict[InGameCharacter, int]]
        netplay: Optional[Metadata.Player.Netplay]

        class Netplay:
            code: Optional[str]
            name: Optional[str]

class Start:
    is_teams: bool
    players: Tuple[Optional[Start.Player], ...]
    random_seed: int
    stage: Stage
    is_pal: Optional[bool]
    is_frozen_ps: Optional[bool]

    class Player:
        character: CSSCharacter
        type: Start.Player.Type
        stocks: int
        costume: int
        team: Optional[Start.Player.Team]
        tag: Optional[str]

        class Type:
            HUMAN: int
            CPU: int

        class Team:
            RED: int
            BLUE: int
            GREEN: int

class End:
    method: End.Method
    lras_initiator: Optional[int]

    class Method:
        INCONCLUSIVE: int
        TIME: int
        GAME: int
        CONCLUSIVE: int
        NO_CONTEST: int

class Frame:
    index: int
    ports: Sequence[Optional[Frame.Port]]
    items: Sequence[Frame.Item]

    class Port:
        leader: Frame.Port.Data
        follower: Optional[Frame.Port.Data]

        class Data:
            @property
            def pre(self) -> Optional[Frame.Port.Data.Pre]: ...
            @property
            def post(self) -> Optional[Frame.Port.Data.Post]: ...

            class Pre:
                state: Union[ActionState, int]
                position: Position
                direction: Direction
                joystick: Position
                cstick: Position
                random_seed: int
                raw_analog_x: Optional[int]
                damage: Optional[float]

            class Post:
                character: InGameCharacter
                state: Union[ActionState, int]
                position: Position
                direction: Direction
                damage: float
                shield: float
                stocks: int
                last_attack_landed: Optional[Union[Attack, int]]
                last_hit_by: Optional[int]
                combo_count: int
                state_age: Optional[float]
                hit_stun: Optional[float]
                airborne: Optional[bool]
                ground: Optional[int]
                jumps: Optional[int]

    class Item:
        type: ItemType
        state: int
        direction: Direction
        velocity: Velocity
        position: Position
        damage: int
        timer: int
        spawn_id: int

class Position:
    x: float
    y: float
    def __init__(self, x: float, y: float) -> None: ...

class Velocity:
    x: float
    y: float
    def __init__(self, x: float, y: float) -> None: ...

class Direction:
    LEFT: int
    RIGHT: int

class Attack:
    pass
