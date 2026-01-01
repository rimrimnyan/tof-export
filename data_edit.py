from abc import ABC, abstractmethod
from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from types import NoneType, UnionType
from typing import Callable, Literal, TypedDict, Union, get_args, get_origin
import re
from re import Pattern

from data_types import AbilityItem, Exportable, Operation, Unspecified, Weapon


AbilityCategory = Literal["normals", "dodges", "skills", "discharges", "passives"]


@dataclass
class ModificationFunc(Exportable):
    """Base class for modifying abilities"""

    def serialize(self):
        if self.__class__ in ParamlessModFunc:
            # serialize as string
            return ParamlessModFunc(self.__class__).name

        if self.__class__ in ParamSingleModFunc:
            # serialize it as { name: value }
            _classname = ParamNModFunc(self.__class__).name

            _fields = fields(self)

            if len(_fields) > 1:
                raise ValueError(f"Multiple fields found on {self.__class__.__name__}!")

            for f in _fields:
                _f_val = getattr(self, f.name)

                # if initially saved as ParamNModFunc, try parsing value
                if isinstance(_f_val, dict):
                    for _val in _f_val.values():
                        return {_classname: _val}

                return {_classname: _f_val}

        if self.__class__ in ParamNModFunc:
            # serialize it as { name: kwargs }
            _classname = ParamNModFunc(self.__class__).name

            d = {}

            for f in fields(self):
                f_val = getattr(self, f.name)

                # skip serializing defaults
                if f.default_factory is not MISSING and f_val == f.default_factory():
                    continue
                if f.default is not MISSING and f_val == f.default:
                    continue

                d[f.name] = self._serialize_to(f.type, f_val)
            return {_classname: d}

        raise ValueError(f"Cannot serialize class {self.__class__.__name__}")

    @classmethod
    def deserialize(cls, item: dict[str, dict | str | int | list] | str):
        # if item is str, then it is paramless
        if isinstance(item, str):
            if item in ParamlessModFunc.__members__:
                return ParamlessModFunc[item].value()
            raise ValueError(f"Invalid item {item}")

        # grab class name to get actual class
        classname = list(item.keys())[0]

        if classname in ParamSingleModFunc.__members__:
            E = ParamSingleModFunc[classname]
            _cls = E.value
            arg = item[E.name]

            if isinstance(arg, dict):
                # compatibility for when it was initially saved as ParamNModfunc
                if len(arg) > 1:
                    raise ValueError(f"More than one value in {arg}!")
                for val in arg.values():
                    return _cls(val)

            return _cls(arg)

        if classname in ParamNModFunc.__members__:
            E = ParamNModFunc[classname]
            _cls = E.value
            item = item[E.name]

            d = {}

            for f in fields(_cls):
                f_val = item.get(f.name, Unspecified())

                if isinstance(f_val, Unspecified):
                    continue

                d[f.name] = _cls._deserialize_as(f.type, f_val)

            return _cls(**d)

        raise ValueError(f"Cannot find appropriate class for {item}")


@dataclass
class TextModi(ModificationFunc):
    """
    A text formatting added to an input text.
    Can be used as 'Modification', in which case, it is applied to the Ability description.
    """

    @abstractmethod
    def __call__(self, text: str) -> str: ...


@dataclass
class AbilityModi(ModificationFunc):
    "Allows modifying fields other than description"

    @abstractmethod
    def __call__(
        self,
        weapon: Weapon,
        ability: AbilityItem,
        from_category: AbilityCategory,
    ): ...


#####


@dataclass
class Remove(TextModi):
    "Removes the specified text or regex"

    pattern: str

    def __call__(self, text: str) -> str:
        new_text = re.sub(self.pattern, "", text, flags=re.DOTALL)

        if text == new_text:
            raise ValueError(f"Failed to remove '{self.pattern}' on text '{text}'")

        return new_text


@dataclass
class InsertNewlines(TextModi):
    "Inserts newlines before each matched regex"

    regex: str


@dataclass
class Strip(TextModi):
    "Strips leading and trailing whitespaces"

    def __call__(self, text: str) -> str:
        return text.strip()


@dataclass
class Move(AbilityModi):
    "Move a part of Ability description into another category"

    to: AbilityCategory
    "To which ability category"

    regex: str | None = field(default=None)
    """
    Regex capturing part of ability description.
    If not specified, just moves the whole ability itself.
    Must capture all text that must be removed!
    Perform post formatting in post_format to remove text in the actual captured description.
    """
    post_format: TextModi | list[TextModi] = field(default_factory=Strip)
    "List post-formatting functions to apply"

    name: str | None = field(default=None)
    "The new name of the moved ability. Must be specified if regex is also specified!"

    icon: str | None = field(default=None)
    "The new icon"

    control: list[Operation] = field(default_factory=list)
    "The new control"

    def __call__(
        self,
        weapon: Weapon,
        ability: AbilityItem,
        from_category: AbilityCategory,
    ):
        if self.regex is None:
            # just move the ability
            ab_list: list[AbilityItem] = getattr(weapon, from_category)
            ab_list.remove(ability)

            to_ab_list: list[AbilityItem] = getattr(weapon, self.to)
            to_ab_list.append(ability)
            return

        # move part of ability description
        m = re.search(self.regex, ability.desc, re.DOTALL)
        if not m:
            raise ValueError(f"Regex '{self.regex}' did not match anything!")
        captured_desc = m.group(0)

        pformats = (
            self.post_format
            if isinstance(self.post_format, list)
            else [self.post_format]
        )
        for f in pformats:
            captured_desc = f(captured_desc)

        new_ab = AbilityItem(
            name=self.name or ability.name,
            desc=captured_desc,
            icon=self.icon or ability.icon,
            # control=self.control or ability.control,
        )

        to_ab_list = getattr(weapon, self.to)
        to_ab_list.append(new_ab)

        # update original desc
        ability.desc = re.sub(self.regex, "", ability.desc, flags=re.DOTALL)


@dataclass
class Modify(AbilityModi):
    "Replaces the specified fields in the Ability"

    name: str | None = field(default=None)
    desc: str | None = field(default=None)
    icon: str | None = field(default=None)
    control: list[Operation] | None = field(default=None)

    def __call__(
        self, weapon: Weapon, ability: AbilityItem, from_category: AbilityCategory
    ):
        if self.name is not None:
            ability.name = self.name
        if self.desc is not None:
            ability.desc = self.desc
        if self.icon is not None:
            ability.icon = self.icon
        if self.control is not None:
            ability.control = self.control


@dataclass
class Previous(ModificationFunc):
    "A special marker specifying that we should use the previous modification"

    def serialize(self):  # type: ignore
        return "PREVIOUS"

    @classmethod
    def deserialize(cls, *_):  # type: ignore
        return cls()


###


class ParamlessModFunc(Enum):
    STRIP = Strip
    PREVIOUS = Previous


class ParamSingleModFunc(Enum):
    REMOVE = Remove


class ParamNModFunc(Enum):
    REMOVE = Remove
    MOVE = Move
    MODIFY = Modify


#####

WeaponName = str
AbilityName = str
AbilityOrMany = (
    AbilityName
    | Literal["NORMALS", "DODGES", "SKILLS", "DISCHARGES", "*"]
    | Literal["INFO"]
)

_ModificationDict = dict[
    WeaponName,
    dict[
        AbilityOrMany,
        ModificationFunc | list[ModificationFunc],
    ],
]


@dataclass
class Modification(Exportable):
    "Class for loading, editing, and saving modifications"

    mods: _ModificationDict

    def serialize(self):
        return self._serialize_to(_ModificationDict, self.mods)

    @classmethod
    def deserialize(cls, item: dict[str, dict | str | int | list]):
        d = cls._deserialize_as(_ModificationDict, item)
        return cls(mods=d)

    def add_shatter(self):
        pass


def _apply_mod_single(
    modi: ModificationFunc | list[ModificationFunc],
    weapon: Weapon,
    ability: AbilityItem,
    ability_category: AbilityCategory,
):
    if not isinstance(modi, list):
        modi = [modi]

    for _modi in modi:
        if isinstance(_modi, TextModi):
            ability.desc = _modi(ability.desc)
        elif isinstance(_modi, AbilityModi):
            _modi(weapon, ability, ability_category)
        else:
            raise ValueError(f"Invalid item {_modi}")


def _apply_mod_multi(
    modi: ModificationFunc | list[ModificationFunc],
    weapon: Weapon,
    abilities: list[AbilityItem],
    ability_categories: AbilityCategory | list[AbilityCategory],
):
    if isinstance(ability_categories, str):
        for ability in abilities:
            _apply_mod_single(modi, weapon, ability, ability_categories)
    else:
        for ability, ability_cat in zip(abilities, ability_categories):
            _apply_mod_single(modi, weapon, ability, ability_cat)


def apply_mod(weapons: list[Weapon], mods: _ModificationDict):
    weapon_name_d = {wpn.char: wpn for wpn in weapons}
    weapon_ability_d: dict[str, dict[str, tuple[AbilityItem, AbilityCategory]]] = {}

    for wpn in weapons:
        weapon_ability_d[wpn.char] = {}
        for ab in wpn.normals:
            weapon_ability_d[wpn.char][ab.name] = (ab, "normals")
        for ab in wpn.dodges:
            weapon_ability_d[wpn.char][ab.name] = (ab, "dodges")
        for ab in wpn.skills:
            weapon_ability_d[wpn.char][ab.name] = (ab, "skills")
        for ab in wpn.discharges:
            weapon_ability_d[wpn.char][ab.name] = (ab, "discharges")

    for _wpn_name in mods:
        previous_modi = None
        weapon = weapon_name_d[_wpn_name]

        for _ab_name in mods[_wpn_name]:
            modi = mods[_wpn_name][_ab_name]
            if isinstance(modi, Previous):
                if previous_modi is None:
                    raise ValueError(
                        "Cannot use PREVIOUS when no previously used modification!"
                    )
                modi = previous_modi

            match _ab_name:
                case "NORMALS":
                    _apply_mod_multi(modi, weapon, weapon.normals, "normals")
                case "DODGES":
                    _apply_mod_multi(modi, weapon, weapon.dodges, "dodges")
                case "SKILLS":
                    _apply_mod_multi(modi, weapon, weapon.dodges, "skills")
                case "DISCHARGES":
                    _apply_mod_multi(modi, weapon, weapon.dodges, "discharges")
                case "*":
                    _ablist, _abcats = zip(*weapon_ability_d[weapon.char].values())
                    _apply_mod_multi(modi, weapon, _ablist, _abcats)  # type: ignore
                case _:
                    (ability, ability_cat) = weapon_ability_d[_wpn_name][_ab_name]
                    _apply_mod_single(modi, weapon, ability, ability_cat)

            previous_modi = modi

    print("`apply_mod` Done!")
