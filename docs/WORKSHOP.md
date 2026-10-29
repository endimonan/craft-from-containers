# Workshop packaging and presentation

- Repository: https://github.com/endimonan/craft-from-containers
- Workshop item: not published yet. The first upload creates it.
- Mod ID: `BSCCraftFromContainers`
- Mod version: `0.1.0`
- Target game: `42.21.0`
- Requires: Base Stock Counter, mod ID `BaseStockCounter`, Workshop ID `3823984685`
- Visibility in `workshop.txt`: public. Switch it to `friendsOnly` or `private` before the first upload for a private trial.

## Upload layout

The local uploader directory is `%USERPROFILE%/Zomboid/Workshop/BSCCraftFromContainers`:

~~~text
BSCCraftFromContainers/
  workshop.txt
  preview.png
  Contents/
    mods/
      BSCCraftFromContainers/
        common/
        42/
          mod.info
          icon.png
          poster.png
          media/
~~~

The runtime package has 23 files. With the preview and metadata, the uploader folder has 25 files.

`workshop.txt` uses version 1, one description entry per line, Steam BBCode, valid tags and public visibility. It has no `id` line until the first upload. The description is English only; the in-game PT-BR translation stays in the mod.

## Art

`preview.png` and `poster.png` are 512 × 512; the mod-list `icon.png` is 128 × 128. `docs/images/how-it-works.png` (1200 × 630) is a gallery image for the Steam page and the README, not a runtime file. The editable SVGs are in `tools/`. To regenerate every PNG, run `npm ci --ignore-scripts`, then `npm run images`.

The mod adds no items, tiles or world objects, so it has no item icons or sprites.

## Tools

- `python tools/package.py` builds `dist/BSCCraftFromContainers-0.1.0-review.zip` with documentation, art and a hash manifest.
- `python tools/prepare-workshop.py [new-folder]` stages a new upload folder and `dist/BSCCraftFromContainers-0.1.0-workshop.zip`, checking that source, folder and ZIP hashes match. It never overwrites an existing folder, so a staged ID and local edits survive. It refuses to stage into `Zomboid/Workshop` while the test copy in `Zomboid/mods` exists: the game would list two mods with the same ID.
- `python tools/check-workshop.py [folder]` runs the installed game's own `workshop.txt` reader and content/PNG validator without contacting Steam. It also checks the English description, the Base Stock Counter requirement and the expected item ID.

Dry run that leaves the real Zomboid folder alone:

~~~powershell
python tools/prepare-workshop.py .runtime/Zomboid/Workshop/BSCCraftFromContainers
python tools/check-workshop.py .runtime/Zomboid/Workshop/BSCCraftFromContainers
~~~

## First upload

1. Pass the in-game checks in [TESTING.md](TESTING.md). Runtime changes need that evidence; presentation-only changes don't.
2. Delete the test copy at `%USERPROFILE%/Zomboid/mods/BSCCraftFromContainers`.
3. Run `prepare-workshop.py`, then `check-workshop.py`, with no arguments.
4. In the game, open **Workshop → Create and update items**, select BSCCraftFromContainers and submit. The game uploads the folder, not the ZIP.
5. Copy the new `id=` line from the staged `workshop.txt` into the repository's `workshop.txt`, and add the ID to this file and the README.
6. On the item's Steam page, add Base Stock Counter (3823984685) under **Add/Remove Required Items**, and upload `docs/images/how-it-works.png` to the gallery.

For later updates keep the item ID. Never create a second item or upload a fork.
