# tof-export

A repository for exported TOF assets (json and png files), with focus on TOF Warp server.
This repository contains instructions and scripts for searching specific texts and assets.

## Exporting Game Files

You may get access to the game files by exporting them.
FModel, UnrealExporter, or Ue4Export may be used to export the game files.
For this repository, [Ue4Export](https://github.com/CrystalFerrai/Ue4Export) was used since it allowed outputting json and png files.

```bat
REM export-tof.bat
@Ue4Export "X:\path\to\Paks" TowerOfFantasy "tof-assetlist.txt" "X:\path\to\Output-UEx" --key 0x6E6B325B02B821BD46AF6B62B1E929DC89957DC6F8AA78210D5316798B7508F8
```

```txt
# tof-assetlist.txt
# Note the use of forward slashes!

[Auto]
Hotta/Content/L10N/en/*
Hotta/Content/Localization/Game/en/*
Hotta/Content/Resources/*
```

Exporting may take a while and can be let run in the background while working on something else.

## Searching Text

To search text within json files, using `sqlite` is highly recommended.

### sqlite

An sqlite database storing all the json content and path can be created to make searching text fast. We insert into the database first before performing searches. Refer to `search.py` script for this. Creating the sqlite database from existing output directory can take hours (took around 5 hours on mine).

```bash
python search.py 'KING'
```

### ripgrep

A naive way to search text throughout the approximately 320k json files. If only performing a one-time search for a string, then this is fine. However, searching with `sqlite` and `ugrep` should be faster if searching multiple times.

```bash
rg --threads 4 'KING'
```

### ugrep

Slightly faster than `ripgrep`, but way slower than `sqlite`. First, build the index (should only be ran once and may take hours):

```bash
ugrep-indexer.exe -I -v
```

Then for subsequent searches:

```bash
ug -J4 --index -I 'KING'
```

## FAQ

1. How do I install `package`?

    Make sure you have [choco](https://chocolatey.org/install) (or another package manger) installed.

    ```bash
    choco install package
    ```

2. What is the 'Paks' folder?

    Look on the directory where you installed TOF. Inside, it should be on `Client\WindowsNoEditor\Hotta\Content\Paks`.
    For launcher version, it can be `E:\TowerOfFantasy_Global\Client\WindowsNoEditor\Hotta\ContentPaks`

3. Can't you just give a compressed file download or upload all the files in this repository?

    The asset files are around 70 GB total.
    Even after compressing to 40 GB, it is well above the 2 GB limit for GitHub Releases.
    And no... please don't ask me to push the asset files to the repository.

## Navigation

This is for my personal uses since there are some files I need to go back and forth to check things with.
If you also have the exported assets, clicking on this link should jump to the correct json file.

### Weapon Description

- [Static Weapon Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\StaticWeaponDataTable_MMO.json)
- [Imitation Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\DT_Imitation_MMO.json)
- [Weapon Upgrade Star Data](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable\WeaponUpgradeStarData_MMO.json)
- [Gameplay Ability Tips Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance\GameplayAbilityTipsDataTable_Balance.json)
- [Skill Update Tips](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance\Skill\SkillUpdateTips_balance.json)

### Suppressor Level

- [Suppressor Effect Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\DT_SuppressorEffect_MMO.json)

### Equipment

- [Equipment Enhancement Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\EquipStrengthenDataTable_MMO.json)

### Server Level

- [Server Level Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\ServerLevelDataTable_MMO.json)
