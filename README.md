# tof-export

A repository for exported TOF assets (json and png files), with focus on TOF Warp server.
Datamined texts and files can be found here.

## Obtaining Game Files

You may get access to the game files by [exporting](#exporting) or [downloading](#downloading) them at the releases page.

### Exporting

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

### Downloading

A compressed archive can be downloaded at (#TODO).
Only the following folders were of interest:

- Hotta/Content/L10N/en/*
- Hotta/Content/Localization/Game/en/*
- Hotta/Content/Resources/*

If directories aside from the ones listed above are required, then a manual [export](#exporting) is required since this repository only provides the assets found on those folders.

## Searching Text

To search text within json files, using `sqlite` is highly recommended.

### sqlite

An sqlite database storing all the json content and path can be created to make searching text fast. We insert into the database first before performing searches. Refer to `search.py` script for this. Creating the sqlite database from existing output directory can take hours (took around 5 hours on mine), as such a release of sqlite.db file is provided (#TODO).

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

1. The release files are compressed (.tar.zst). How do I decompress them?

    ```bash
    #TODO
    ```

2. How do I install `package`?

    Make sure you have [choco](https://chocolatey.org/install) (or another package manger) installed.

    ```bash
    choco install package
    ```

## Other stuff

- [Static Weapon Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\StaticWeaponDataTable_MMO.json)
- [Imitation Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_MMO\DT_Imitation_MMO.json)
- [Weapon Upgrade Star Data](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable\WeaponUpgradeStarData_MMO.json)
- [Gameplay Ability Tips Data Table](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance\GameplayAbilityTipsDataTable_Balance.json)
- [Skill Update Tips](Output-UEx\Hotta\Content\Resources\CoreBlueprints\DataTable_Balance\Skill\SkillUpdateTips_balance.json)
