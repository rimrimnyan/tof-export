import json
import os
import re
import shutil
from decimal import Decimal
from os.path import basename
from typing import Literal

from data_types import (
    Abilities,
    AbilityItem,
    Advancements,
    Category,
    CharRefEntry,
    Element,
    NameIntroEntry,
    Operation,
    Weapon,
)
from helper import compress_dir, format_dec, kebab_case


def datatable_path(json_file: str):
    dirs = [
        r"Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO",
        r"Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable",
        r"Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance",
        r"Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance\Skill",
    ]

    for dir in dirs:
        fpath = rf"{dir}\{json_file}.json"
        if os.path.exists(fpath):
            return fpath

    raise ValueError(f"Cannot find file {json_file}.json")


with open(datatable_path("StaticWeaponDataTable_MMO"), "rb") as f:
    DTSW: dict = json.loads(f.read())[0]
with open(datatable_path("DT_Imitation_MMO"), "rb") as f:
    DTI: dict = json.loads(f.read())[0]
with open(datatable_path("WeaponUpgradeStarData_MMO"), "rb") as f:
    DTWUS: dict = json.loads(f.read())[0]
with open(datatable_path("GameplayAbilityTipsDataTable_Balance"), "rb") as f:
    DTGAT: dict = json.loads(f.read())[0]
with open(datatable_path("SkillUpdateTips_balance"), "rb") as f:
    DTSUT: dict = json.loads(f.read())[0]


ref_names_dir = os.listdir(
    # r"Output-UEx\Hotta\Content\Resources\Abilities\Buff\Player\WeaponSSR"
    r"Output-UEx\Hotta\Content\Resources\Abilities\Player"
)


def local_asset(path: str):
    return path.replace(r"/Game", r"Output-UEx/Hotta/Content").split(".")[0] + ".png"


def get_name_intro_entries() -> list[NameIntroEntry]:
    entries = []
    pattern = re.compile(
        r"^GA_F[Pp]layer(.*?)(?:ChangeSkill|BigSkill|Skill|Melee|Evade)"
    )

    for key in DTSW["Rows"]:
        key: str

        lowkey = key.lower()

        if lowkey.endswith(
            ("2", "3", "fashion", "imitation", "ui", "show")
        ) or lowkey.startswith(("breakfate", "dwsk")):
            continue

        try:
            weapon_name = DTSW["Rows"][key]["ItemName"]["LocalizedString"]
            weapon_intro = DTSW["Rows"][key]["WeaponMatchDes"]["LocalizedString"]
            weapon_image = local_asset(
                DTSW["Rows"][key]["ItemLargeIcon"]["AssetPathName"]
            )
        except KeyError:
            print(f"`get_name_intro_entries` Cant find weapon info for '{key}'")
            continue

        name_image_path = DTSW["Rows"][key]["ItemNameImage"]["AssetPathName"]

        # add weapon refs
        extra_ref_name = ""
        match = pattern.match(DTSW["Rows"][key]["WeaponSkillList"][0])
        if match:
            extra_ref_name = match.group(1)

        # add other weapon info
        category = Category(
            DTSW["Rows"][key]["WeaponTypeData"]["WeaponCategory"].split("::")[1]
        )
        element = Element(
            DTSW["Rows"][key]["WeaponTypeData"]["WeaponElementType"].split("::")[1]
        )

        entries.append(
            NameIntroEntry(
                weapon_name,
                weapon_intro,
                weapon_image,
                element,
                category,
                name_image_path,
                extra_ref_name,
            )
        )
    return entries


def get_char_ref_entries() -> list[CharRefEntry]:
    entries = []

    ref_name_map = {x.lower(): x for x in ref_names_dir}

    for key in DTI["Rows"]:
        key: str

        if key.endswith("L1"):
            continue

        row = DTI["Rows"][key]

        char_name = row["Name"]["LocalizedString"]
        char_vertical_banner_image = local_asset(row["Painting"]["AssetPathName"])
        char_centered_image = local_asset(row["CardAdvPage"]["AssetPathName"])

        name_image_path = row["Name3Picture"]["AssetPathName"]

        ref_names = set()
        # Add char name as ref_name
        ref_names.add(char_name)
        # Add part of Montage Asset Path Name
        ref_name_mon = row["Montage"]["AssetPathName"].split("/")[7]
        ref_name = ref_name_map.get(ref_name_mon.lower(), None)
        if ref_name:
            ref_names.add(ref_name)
        else:
            ref_names.add(ref_name_mon)
        # Add avatar id
        avatar_id = row.get("AvatarId")
        if avatar_id:
            ref_names.add(avatar_id)
        # Add avatar id from L1
        if f"{key}L1" in DTI["Rows"]:
            l1_avatar_id = DTI["Rows"][f"{key}L1"].get("AvatarId")
            if l1_avatar_id:
                ref_names.add(l1_avatar_id)
        # Add weapon id
        weapon_id = row.get("WeaponId")
        if weapon_id:
            ref_names.add(weapon_id.split("_")[0])

        if "None" in ref_names:
            ref_names.remove("None")

        entries.append(
            CharRefEntry(
                char_name,
                char_vertical_banner_image,
                char_centered_image,
                ref_names,
                name_image_path,
            )
        )

    return entries


def get_effect_figures(remould_params: dict) -> list[str]:
    values = []

    loaded_jsons = {}
    for item in remould_params:
        mul = Decimal(str(item["Value"]))
        row_name = item["Curve"]["RowName"]
        curve_table = item["Curve"]["CurveTable"]

        if row_name == "None" or curve_table is None:
            values.append(format_dec(mul))
            continue

        figpath = curve_table["ObjectPath"].rstrip(".0123456789")

        if figpath not in loaded_jsons:
            with open(rf"Output-UEx/{figpath}.json", "rb") as f:
                loaded_jsons[figpath] = json.loads(f.read())[0]

        val = (
            Decimal(str(loaded_jsons[figpath]["Rows"][row_name]["Keys"][0]["Value"]))
            * mul
        )
        values.append(format_dec(val))
    return values


def get_advancement_entries() -> list[Advancements]:
    entries = []

    done = set()
    skip = set()
    for key in DTWUS["Rows"]:
        key: str
        if key.startswith("breakfate"):
            continue

        ref = key.split("_")[0]

        if ref in done or ref in skip:
            continue

        #
        key_base = key.rstrip("0123456789")
        adv = {}

        for i in range(1, 16):
            # TODO range(0, 16)
            key_adv = f"{key_base}{i}"

            # check if first if up to 15 adv
            if f"{key_base}15" not in DTWUS["Rows"]:
                print(f"Not up to 15: {key_base}")
                raise ValueError()

            if key_adv not in DTWUS["Rows"]:
                print(
                    f"`get_advancement_entries` Incomplete advancement info for '{key_base}'"
                )
                skip.add(ref)
                break

            desc: str = DTWUS["Rows"][key_adv]["RemouldDetail"]["LocalizedString"]
            params = DTWUS["Rows"][key_adv]["RemouldDetailParams"]

            if params:
                desc = desc.format(*get_effect_figures(params))

            adv[i] = desc

        entries.append(Advancements(ref, adv))
        done.add(ref)
    return entries


def get_ability_entries() -> dict[str, Abilities]:
    pattern = re.compile(
        r"^GA_F[Pp]layer(.*?)(?:ChangeSkill|BigSkill|Skill|Melee|Evade)"
    )

    entries: dict[str, Abilities] = {}
    skip = set()

    for key in DTGAT["Rows"]:
        key: str

        # skip breakfate, artifact abilities
        lowkey = key.lower()
        if lowkey.startswith(("ga_spawn", "ga_artifact")) or lowkey.endswith(
            ("breakfate")
        ):
            continue

        match = pattern.match(key)
        if match:
            ref_name = match.group(1)
        else:
            continue

        if ref_name in skip:
            continue

        # prioritize `_Balance` version if it exists
        if not key.endswith("_Balance") and f"{key}_Balance" in DTGAT["Rows"]:
            continue

        if ref_name not in entries:
            entries[ref_name] = Abilities(ref_name=ref_name)

        row_name = DTGAT["Rows"][key]["Scores"]["Curve"]["RowName"]
        if row_name == "None":
            # infer row_name from key
            if "changeskill" in lowkey:
                row_name = "WeaponChangeSkill"
            elif "skill" in lowkey:
                row_name = "WeaponSkill"
            elif "evade" in lowkey:
                row_name = "WeaponEvade"
            elif "melee" in lowkey:
                row_name = "WeaponMelee"

        match row_name:
            case "WeaponSkill":
                append_to = entries[ref_name].skill
            case "WeaponMelee":
                append_to = entries[ref_name].attack
            case "WeaponEvade":
                append_to = entries[ref_name].dodge
            case "WeaponChangeSkill":
                append_to = entries[ref_name].discharge
            case _:
                raise ValueError(f"Invalid RowName {row_name}")

        branch_struct = DTGAT["Rows"][key]["GABranchStruct"]
        n = len(branch_struct)

        for item in branch_struct:
            branch_name = item["Value"]["Name"].get("LocalizedString", "")
            if not branch_name and n == 1:
                branch_name = DTGAT["Rows"][key]["Name"].get("LocalizedString", "")

            if row_name in ("WeaponMelee", "WeaponEvade"):
                # exclude Melee/Dodge abilities that dont have operation
                # this will exclude Sneak Attack and even old values
                if not item["Value"]["Operations"]:
                    # print(
                    #     f"`get_ability_entries` Skipping operationless ability '{branch_name}' of '{ref_name}'"
                    # )
                    continue

            control = [Operation(x) for x in item["Value"]["Operations"]]
            if control and Operation.AND in control:
                skip_this = False
                # check invalid operation combination
                for op_idx, op in enumerate(control):
                    if (
                        op == Operation.AND
                        and control[op_idx - 1] == control[op_idx + 1]
                    ):
                        print(
                            f"`get_ability_entries` Skipping invalid operation: '{branch_name}' of '{ref_name}' with {[x.name for x in control[op_idx - 1 : op_idx + 2]]}"
                        )
                        skip_this = True
                        break

                if skip_this:
                    continue

            # no duplicates names
            if branch_name in [x.name for x in append_to]:
                continue

            branch_desc = item["Value"]["Desc"].get("LocalizedString", "")
            if not branch_desc and n == 1:
                branch_desc = DTGAT["Rows"][key]["Desc"].get("LocalizedString", "")

            # replace values in description
            if r"{" in branch_desc:
                sut_key = item["Key"] + "_"
                # sut_key = item["Value"]["Name"].get("Key", "").rstrip("name")
                if not sut_key:
                    raise ValueError(f"Cannot find skill values for {key}")

                if f"{sut_key}1" not in DTSUT["Rows"]:
                    print(
                        f"`get_ability_entries` Cannot find values for {ref_name} with key {sut_key}"
                    )
                    continue

                ability_values = []
                i = 1
                while f"{sut_key}{i}" in DTSUT["Rows"]:
                    ab_val = Decimal(
                        str(DTSUT["Rows"][f"{sut_key}{i}"]["Keys"][0]["Value"])
                    )
                    ability_values.append(format_dec(ab_val))
                    i += 1

                try:
                    branch_desc = branch_desc.format(*ability_values)
                except (
                    IndexError
                ):  # weirdly only happens with Fiona due to missing figures
                    print(
                        f"`get_ability_entries` Skipping '{ref_name}' due to value substitution error"
                    )
                    skip.add(ref_name)
                    continue

            branch_icon = local_asset(item["Value"]["Icon"]["AssetPathName"])

            append_to.append(
                AbilityItem(
                    name=branch_name,
                    desc=branch_desc,
                    icon=branch_icon,
                    control=control,
                )
            )
    return entries


def get_weapons() -> list[Weapon]:
    weapons = []

    name_intro_d = {entry.name_image_path: entry for entry in get_name_intro_entries()}
    adv_d = {entry.ref_name.lower(): entry for entry in get_advancement_entries()}
    ab_d = {key.lower(): entry for key, entry in get_ability_entries().items()}

    for char_ref in get_char_ref_entries():
        # resolve entry via name image path first
        name_intro = name_intro_d.get(char_ref.name_image_path, None)

        # try resolve using ref_name
        if not name_intro:
            for _entry in name_intro_d.values():
                if (
                    _entry.extra_ref_name
                    and _entry.extra_ref_name in char_ref.ref_names
                ):
                    name_intro = _entry

        if not name_intro:
            print(
                f"`get_weapons` Cannot match character: {char_ref.char_name} {char_ref.ref_names}"
            )
            # Can skip safely since purple weapons are not present in MMO
            continue

        all_ref_names = char_ref.ref_names
        if name_intro.extra_ref_name:
            all_ref_names.add(name_intro.extra_ref_name)

        adv_try_entries = [adv_d.get(x.lower(), None) for x in all_ref_names]
        adv: Advancements | None = next(
            (x for x in adv_try_entries if x is not None), None
        )

        ab_try_entries = [ab_d.get(x.lower(), None) for x in all_ref_names]
        abilities: Abilities | None = next(
            (x for x in ab_try_entries if x is not None), None
        )

        if not adv:
            raise ValueError(f"Advancement entry missing for {char_ref.char_name}")
        if not abilities:
            raise ValueError(f"Ability entry missing for {char_ref.char_name}")

        weapons.append(
            Weapon(
                char=char_ref.char_name,
                char_banner_image=char_ref.char_vertical_banner_image,
                char_centered_image=char_ref.char_centered_image,
                #
                name=name_intro.weapon_name,
                image=name_intro.weapon_image,
                intro=name_intro.weapon_intro,
                element=name_intro.element,
                category=name_intro.category,
                #
                normals=abilities.attack,
                dodges=abilities.dodge,
                skills=abilities.skill,
                discharges=abilities.discharge,
                #
                enhancement=adv.adv,
                #
                ref_names=all_ref_names,
            )
        )

    return weapons


def export_image_from_instance(
    inst: Weapon | AbilityItem,
    key: Literal["char_banner_image", "char_centered_image", "image", "icon"],
    dst: str,
    dst_trim: str = "",
):
    """
    Copies the image to dst and modifies the path in the instance
    """

    src = getattr(inst, key)
    if not os.path.exists(dst):
        shutil.copy(src, dst)

    if dst_trim:
        dst = dst.replace(dst_trim, "")

    setattr(inst, key, dst)


def _export_weapons(output_dir: str):
    char_image_dir = f"{output_dir}/images/char"
    weapon_image_dir = f"{output_dir}/images/weapon"
    ability_image_dir = f"{output_dir}/images/ability"

    for dir in [
        char_image_dir,
        weapon_image_dir,
        ability_image_dir,
    ]:
        os.makedirs(dir, exist_ok=True)

    for wpn in get_weapons():
        char = kebab_case(wpn.char)

        # weapon and char images
        banner_image_exported = f"{char_image_dir}/{char}-banner.png"
        char_image_exported = f"{char_image_dir}/{char}.png"
        weapon_image_exported = f"{weapon_image_dir}/{char}.png"

        export_image_from_instance(
            wpn, "char_banner_image", banner_image_exported, output_dir
        )
        export_image_from_instance(
            wpn, "char_centered_image", char_image_exported, output_dir
        )
        export_image_from_instance(wpn, "image", weapon_image_exported, output_dir)

        # ability images
        for ability in wpn.normals + wpn.dodges + wpn.skills + wpn.discharges:
            ability_image_exported = f"{ability_image_dir}/{basename(ability.icon)}"
            export_image_from_instance(
                ability, "icon", ability_image_exported, output_dir
            )

        # weapon json
        with open(f"{output_dir}/{char}.json", "w") as f:
            f.write(json.dumps(wpn.serialize(), indent=4))


def _export_icons(output_dir: str):
    element_image_dir = f"{output_dir}/images/element"
    category_image_dir = f"{output_dir}/images/category"

    for dir in [
        element_image_dir,
        category_image_dir,
    ]:
        os.makedirs(dir, exist_ok=True)

    # element icons
    for ein, eout in [
        ("fire", "flame"),
        ("thunder", "volt"),
        ("physics", "physical"),
        ("ice", "frost"),
        ("powers", "altered"),
    ]:
        shutil.copy(
            rf"Output-UEx/Hotta/Content/Resources/UI/mingzou/icon/element_{ein}.png",
            f"{element_image_dir}/{eout}.png",
        )

    for cin, cout in [
        ("fangyu", "tank"),
        ("qianggong", "dps"),
        ("zengyi", "sup"),
    ]:
        shutil.copy(
            rf"Output-UEx/Hotta/Content/Resources/UI/mingzou/icon/icon_{cin}.png",
            f"{category_image_dir}/{cout}.png",
        )


def export_assets(
    weapons: bool = True,
    icons: bool = True,
    output_dir: str = "export",
    compress: bool = False,
):
    """
    Export the weapons for use with the website
    """

    if weapons:
        _export_weapons(output_dir)
    if icons:
        _export_icons(output_dir)

    if compress:
        print("Compressing...")
        compress_dir(output_dir, "export.tar.zst", remove_after=True)


if __name__ == "__main__":
    export_assets(
        weapons=True,
        icons=True,
        compress=True,
    )
