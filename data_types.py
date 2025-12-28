from abc import ABC
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, get_args, get_origin


class Unspecified:
    pass


class Element(str, Enum):
    PHYSICAL = "Physics"
    FLAME = "Flame"
    VOLT = "Thunder"
    FROST = "Ice"
    ALTERED = "Superpower"

    def serialize(self):
        return self.name

    @classmethod
    def deserialize(cls, value: str):
        return cls[value]


class Category(str, Enum):
    DPS = "DPS"
    SUPPORT = "SUP"
    TANK = "Tank"

    def serialize(self):
        return self.name

    @classmethod
    def deserialize(cls, value: str):
        return cls[value]


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

    @classmethod
    def deserialize(cls, value: str):
        return cls[value]

    @property
    def sort_value(self):
        if self == Operation.DIRECTIONAL_KEY:
            return 1
        else:
            return self.value


@dataclass
class Exportable(ABC):
    """
    Utility class for exporting stuff
    """

    @classmethod
    def _serialize_to(cls, _type: type, value: Any):
        origin = get_origin(_type)
        args = get_args(_type)

        if hasattr(value, "serialize"):
            return value.serialize()
        elif _type in (str, int, float):
            return value
        elif origin in (list, set):
            return [cls._serialize_to(args[0], x) for x in value]
        elif origin is dict:
            d = {}
            key_type, val_type = args
            for key, val in value.items():
                d[cls._serialize_to(key_type, key)] = cls._serialize_to(val_type, val)
            return d
        else:
            raise ValueError(f"Cannot serialize: {value} with type {_type}")

    def serialize(self):
        d = {}

        for f in fields(self):
            f_val = getattr(self, f.name)
            d[f.name] = self._serialize_to(f.type, f_val)

        return d

    @classmethod
    def _deserialize_as(cls, _type: type, value: str | int | float | dict | list):
        origin = get_origin(_type)
        args = get_args(_type)

        if hasattr(_type, "deserialize"):
            return _type.deserialize(value)
        elif _type in (str, int, float):
            return value
        elif origin is list:
            if len(args) >= 2:
                raise NotImplementedError("Cannot handle union types!")
            return [cls._deserialize_as(args[0], x) for x in value]
        elif origin is set:
            if len(args) >= 2:
                raise NotImplementedError("Cannot handle union types!")
            return set([cls._deserialize_as(args[0], x) for x in value])
        elif origin is dict:
            key_type, val_type = args

            d = {}
            for key, val in value.items():
                d[cls._deserialize_as(key_type, key)] = cls._deserialize_as(
                    val_type, val
                )
            return d

        else:
            raise ValueError(f"Cannot process type {_type}")

    @classmethod
    def deserialize(cls, item: dict[str, dict | str | int | list]):
        d = {}

        for f in fields(cls):
            f_val = item.get(f.name, Unspecified())

            if f_val is Unspecified:
                continue

            d[f.name] = cls._deserialize_as(f.type, f_val)

        return cls(**d)


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

    def __lt__(self, other: "AbilityItem"):
        if not self.control:
            return False
        if not other.control:
            return True

        for x, y in zip(self.control, other.control):
            if x.sort_value != y.sort_value:
                return x.sort_value < y.sort_value

        return len(self.control) < len(other.control)


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
    category: Category = field(default=Category.DPS)

    normals: list[AbilityItem] = field(default_factory=list)
    dodges: list[AbilityItem] = field(default_factory=list)
    skills: list[AbilityItem] = field(default_factory=list)
    discharges: list[AbilityItem] = field(default_factory=list)
    passives: list[AbilityItem] = field(default_factory=list)

    enhancement: dict[int, str] = field(default_factory=dict)

    ref_names: set[str] = field(default_factory=set)

    def __post_init__(self):
        self.normals = sorted(self.normals)
        self.dodges = sorted(self.dodges)
