from abc import ABC
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import get_origin


class Element(str, Enum):
    PHYSICAL = "Physics"
    FLAME = "Flame"
    VOLT = "Thunder"
    FROST = "Ice"
    ALTERED = "Superpower"

    def serialize(self):
        return self.name


class Category(str, Enum):
    DPS = "DPS"
    SUPPORT = "SUP"
    TANK = "Tank"

    def serialize(self):
        return self.name


class Operation(int, Enum):
    ATTACK = 0
    JUMP = 1
    DODGE = 2
    SNEAK = 3
    DIRECTIONAL_KEY = 4
    HOLD_ATTACK = 5
    AND = 6
    NEXT = 7
    HOLD_DODGE = 8

    def serialize(self):
        return self.name


@dataclass
class Exportable(ABC):
    """
    Utility class for exporting stuff
    """

    def serialize(self):
        d = {}

        for f in fields(self):
            origin = get_origin(f.type)
            f_val = getattr(self, f.name)

            if hasattr(f_val, "serialize"):
                d[f.name] = f_val.serialize()

            elif f.type in (str, int, float):
                d[f.name] = f_val

            elif origin is dict:
                _d1 = {}
                for k, v in f_val.items():
                    if hasattr(k, "serialize"):
                        k = k.serialize()
                    if hasattr(v, "serialize"):
                        v = v.serialize()
                    _d1[k] = v

                d[f.name] = _d1
            elif origin in (list, set):
                _l1 = []

                for item in f_val:
                    if hasattr(item, "serialize"):
                        item = item.serialize()
                    _l1.append(item)

                d[f.name] = _l1

            else:
                raise ValueError(f"Unmatched: {f.name} with type {f.type}")

        return d


@dataclass
class NameIntroEntry:
    """
    Information taken from Static Weapon Data Table
    """

    weapon_name: str
    weapon_intro: str
    weapon_image: str
    element: Element
    category: Category
    name_image_path: str

    extra_ref_name: str


@dataclass
class CharRefEntry:
    """
    Information taken from Imitation Data Table
    """

    char_name: str
    char_vertical_banner_image: str
    char_centered_image: str

    ref_names: set[str]

    name_image_path: str


@dataclass
class Advancements:
    ref_name: str
    adv: dict[int, str]


@dataclass
class AbilityItem(Exportable):
    name: str
    desc: str
    icon: str
    control: list[Operation] = field(default_factory=list)


@dataclass
class Abilities(Exportable):
    ref_name: str
    attack: list[AbilityItem] = field(default_factory=list)
    dodge: list[AbilityItem] = field(default_factory=list)
    skill: list[AbilityItem] = field(default_factory=list)
    discharge: list[AbilityItem] = field(default_factory=list)


@dataclass
class Weapon(Exportable):
    char: str = field(default="")
    char_banner_image: str = field(default="")
    char_centered_image: str = field(default="")
    name: str = field(default="")
    image: str = field(default="")
    intro: str = field(default="")
    element: Element = field(default=Element.ALTERED)

    normals: list[AbilityItem] = field(default_factory=list)
    dodges: list[AbilityItem] = field(default_factory=list)
    skills: list[AbilityItem] = field(default_factory=list)
    discharges: list[AbilityItem] = field(default_factory=list)

    enhancement: dict[int, str] = field(default_factory=dict)

    ref_names: set[str] = field(default_factory=set)
