from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Literal, TypedDict
import re
from re import Pattern

from data_types import AbilityItem, Operation, Weapon


AbilityCategory = Literal["normals", "dodges", "skills", "discharges", "passives"]

PREVIOUS: Literal["PREVIOUS"] = "PREVIOUS"


class ModificationFunc(ABC):
    """Base class for modification"""


class TextModi(ABC):
    """
    A text formatting added to an input text.
    Can be used as 'Modification', in which case, it is applied to the Ability description.
    """

    @abstractmethod
    def __call__(self, text: str) -> str: ...


class AbilityModi(ABC):
    "Allows modifying fields other than description"

    @abstractmethod
    def __call__(
        self,
        weapon: Weapon,
        ability: AbilityItem,
        from_category: AbilityCategory,
    ): ...


class Remove(TextModi):
    "Removes the specified text or regex"

    def __init__(self, text_or_pattern: str | Pattern) -> None:
        self.text_or_pattern = text_or_pattern

    def __call__(self, text: str) -> str:
        if isinstance(self.text_or_pattern, str):
            new_text = text.replace(self.text_or_pattern, "")
        else:
            new_text = re.sub(self.text_or_pattern.pattern, "", text, flags=re.DOTALL)

        if text == new_text:
            raise ValueError(f"Failed to remove '{self.text_or_pattern}'")

        return new_text


class InsertNewlines(TextModi):
    "Inserts newlines before each matched regex"

    def __init__(self, regex: str | Pattern) -> None:
        self.regex = regex


class Strip(TextModi):
    "Strips leading and trailing whitespaces"

    def __init__(self) -> None:
        pass

    def __call__(self, text: str) -> str:
        return text.strip()


@dataclass
class Move(AbilityModi):
    "Move a part of Ability description into another category"

    to: AbilityCategory
    "To which ability category"

    regex: Pattern | None = field(default=None)
    """
    Regex capturing part of ability description.
    If not specified, just moves the whole ability itself.
    Must capture all text that must be removed!
    Perform post formatting in post_format to remove text in the actual captured description.
    """
    post_format: list[Callable] = field(default_factory=lambda: [Strip()])
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
        m = re.search(self.regex.pattern, ability.desc, re.DOTALL)
        if not m:
            raise ValueError(f"Regex '{self.regex}' did not match anything!")
        captured_desc = m.group(0)
        for f in self.post_format:
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
        ability.desc = re.sub(self.regex.pattern, "", ability.desc, flags=re.DOTALL)


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


#####

WeaponName = str
AbilityName = str
AbilityOrMany = AbilityName | Literal["NORMALS", "DODGES", "SKILLS", "DISCHARGES", "*"]

_ModificationDict = dict[
    WeaponName,
    dict[
        AbilityOrMany,
        TextModi | AbilityModi | list[AbilityModi | TextModi] | Literal["PREVIOUS"],
    ],
]

MODS: _ModificationDict = {
    "Liu Huo": {
        "In All Directions": Move(
            to="passives",
            regex=re.compile(r"\r\n\r\n.*"),
            post_format=[
                Remove("\r\n\r\n <shuzhi>Passive: Calligraphy Characters</>\r\n"),
                Strip(),
            ],
            name="Calligraphy Characters",
        ),
        "A Spark of Genius": Move(
            to="passives",
            regex=re.compile(r"\r\n.*"),
            name="Fortitude Resonance",
        ),
    },
    "Ji Yu": {
        "Shifting Stars": Move(
            to="passives",
            regex=re.compile(r"\r\n Grants.*"),
            name="Sharp Blade",
        ),
        "Review Board": Remove(re.compile(r"\r\n Grants.*")),
        "Starting Move": PREVIOUS,
    },
}


def _apply_mod_single(
    modi: TextModi | AbilityModi | list[TextModi | AbilityModi],
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
    modi: TextModi | AbilityModi | list[TextModi | AbilityModi],
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
            if modi == PREVIOUS:
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
