"""Type stubs for slippi.id module."""

from enum import IntEnum

class CSSCharacter(IntEnum):
    """Character as selected on the character select screen."""
    CAPTAIN_FALCON: int
    DONKEY_KONG: int
    FOX: int
    GAME_AND_WATCH: int
    KIRBY: int
    BOWSER: int
    LINK: int
    LUIGI: int
    MARIO: int
    MARTH: int
    MEWTWO: int
    NESS: int
    PEACH: int
    PIKACHU: int
    ICE_CLIMBERS: int
    JIGGLYPUFF: int
    SAMUS: int
    YOSHI: int
    ZELDA: int
    SHEIK: int
    FALCO: int
    YOUNG_LINK: int
    DR_MARIO: int
    ROY: int
    PICHU: int
    GANONDORF: int

    @property
    def name(self) -> str: ...

class InGameCharacter(IntEnum):
    """Character as it appears in-game (Zelda/Sheik can change)."""
    pass

class Stage(IntEnum):
    """Stage ID."""
    FOUNTAIN_OF_DREAMS: int
    POKEMON_STADIUM: int
    YOSHIS_STORY: int
    DREAM_LAND_N64: int
    BATTLEFIELD: int
    FINAL_DESTINATION: int

    @property
    def value(self) -> int: ...

class ActionState(IntEnum):
    """Action state IDs."""
    pass

class Item(IntEnum):
    """Item type IDs."""
    pass
