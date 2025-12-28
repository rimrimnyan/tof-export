from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Literal
import re
from re import Pattern

from data_types import AbilityItem, Operation, Weapon


AbilityCategory = Literal["normals", "dodges", "skills", "discharges", "passives"]


class PostFormat(ABC):
    @abstractmethod
    def __call__(self, text: str) -> str: ...


class Remove(PostFormat):
    "Removes the specified text or regex"

    def __init__(self, text_or_pattern: str | Pattern) -> None:
        self.text_or_pattern = text_or_pattern

    def __call__(self, text: str) -> str:
        if isinstance(self.text_or_pattern, str):
            new_text = text.replace(self.text_or_pattern, "")
        else:
            new_text = re.sub(self.text_or_pattern, "", text, flags=re.DOTALL)

        if text == new_text:
            raise ValueError(f"Failed to remove '{self.text_or_pattern}'")

        return new_text


class Strip(PostFormat):
    "Strips leading and trailing whitespaces"

    def __init__(self) -> None:
        pass

    def __call__(self, text: str) -> str:
        return text.strip()


class Modification(ABC):
    pass


@dataclass
class Move(Modification):
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


_mods: dict[str, dict[str, list[Modification]]] = {
    "Liu Huo": {
        "In All Directions": [
            Move(
                to="passives",
                regex=re.compile(r"\r\n\r\n.*"),
                post_format=[
                    Remove("\r\n\r\n <shuzhi>Passive: Calligraphy Characters</>\r\n"),
                    Strip(),
                ],
                name="Calligraphy Characters",
            )
        ],
        "A Spark of Genius": [
            Move(
                to="passives",
                regex=re.compile(r"\r\n.*"),
                name="Fortitude Resonance",
            )
        ],
    },
}


def apply_mod(weapons: list[Weapon], mods: dict[str, dict[str, list[Modification]]]):
    wpn_d = {wpn.char: wpn for wpn in weapons}
    wpn_ab_d = {}
    for wpn in weapons:
        wpn_ab_d[wpn.char] = {}
        for ab in wpn.normals:
            wpn_ab_d[wpn.char][ab.name] = {"obj": ab, "from": "normals"}
        for ab in wpn.dodges:
            wpn_ab_d[wpn.char][ab.name] = {"obj": ab, "from": "dodges"}
        for ab in wpn.skills:
            wpn_ab_d[wpn.char][ab.name] = {"obj": ab, "from": "skills"}
        for ab in wpn.discharges:
            wpn_ab_d[wpn.char][ab.name] = {"obj": ab, "from": "discharges"}

    for _wpn_name in mods:
        weapon = wpn_d[_wpn_name]

        for _ab_name in mods[_wpn_name]:
            _adict = wpn_ab_d[_wpn_name][_ab_name]

            ability = _adict["obj"]
            from_category = _adict["from"]

            for _mod in mods[_wpn_name][_ab_name]:
                if isinstance(_mod, Move):
                    _mod(weapon, ability, from_category)
                else:
                    raise ValueError(f"Invalid item {_mod}")

    print("`apply_mod` Done!")
