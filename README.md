# Craft From Containers (Base Stock)

Craft with what's in nearby containers and anywhere in your base, without hauling everything to your inventory first. Built on top of [Base Stock Counter](https://github.com/endimonan/base-stock-counter): the base is the same shared area you define there. Supports single-player, hosted multiplayer and dedicated servers.

[Contributing](CONTRIBUTING.md) · [Architecture](docs/ARCHITECTURE.md) · [Testing](docs/TESTING.md)

## How it works

- **Nearby:** crafting can use explored containers up to 5 squares away (configurable), on your floor and in the same building. Outdoors counts as one "building", so it never reaches through a wall into another house.
- **Base area:** while you stand inside the Base Stock Counter area, crafting can use explored containers anywhere in it, on every floor, basement included.

The crafting window and item right-click crafts show recipes as craftable using those containers. When the craft starts:

1. The server checks every remote item and brings it to your inventory.
2. The game's own craft runs, exactly like it does with items you carry.
3. What's left of the remote items (tools, partly used items) goes back to the container it came from. Disorganized characters keep them, like vanilla.

In a batch, tools stay with you until the last craft instead of going back and forth. If a craft is cancelled, what was brought over goes back.

Everything else (transfers, healing, light sources, reloading, building, workstations) keeps the vanilla reach.

Containers that are never used:

- Never-opened containers. Using them would make the server generate their loot.
- Locked containers and containers in a safehouse you can't loot.
- Corpses, vehicles, loose items on the floor and other players.
- Bags stored inside containers. Base Stock Counter counts their contents, but crafting only reads the container itself.
- Parts of the base your game hasn't loaded. Nothing is force-loaded.

## Multiplayer

The client only asks. The server decides and moves the items, so everyone sees the same thing through the game's normal item sync.

Before moving anything, the server checks every item in the request against its own state: the container is where the client said, the item is directly in it, the container is explored, not locked, not in a safehouse you can't loot, and either within the nearby radius or in the base area with you standing in it (2 squares of slack for lag). If anything fails, nothing moves, the craft is cancelled, you get a message saying why and the reason goes to the server log. A full inventory doesn't block a craft: the items only pass through it.

Two players reaching for the same item: the server handles one request at a time. The second request finds the item gone and its craft is cancelled. Nothing is duplicated.

Returns are checked the same way, item by item. Anything that can't go back (container gone or full, you walked away) stays in your inventory and you get a message.

## Sandbox options

| Option | Default | What it does |
| --- | --- | --- |
| Craft from the base area | On | Use containers anywhere in the base area while standing in it |
| Nearby radius | 5 | Squares around you, same floor and building. 0 turns it off |
| Base container limit | 256 | Most base containers offered at once, closest first. Lower it if the crafting window gets slow |

## Installation and removal

Target version: **Project Zomboid 42.21.0**. Requires **Base Stock Counter**. The game won't enable this mod without it.

Not on the Workshop yet. For local testing, copy `Contents/mods/BSCCraftFromContainers` into `%USERPROFILE%/Zomboid/mods/BSCCraftFromContainers`, keeping `42` and `common`, and make sure Base Stock Counter is installed too. Enable both, then start the save.

For a server, both mods go in the list:

~~~ini
Mods=BaseStockCounter;BSCCraftFromContainers
~~~

To remove it, stop the save or server, disable the mod and start again. The mod saves nothing: no ModData, items, recipes or world objects. Items it moved are ordinary items wherever they ended up. Its sandbox options are ignored once it's gone. Base Stock Counter keeps working on its own.

## Source layout

The runtime is Lua-only, under `Contents/mods/BSCCraftFromContainers/42/media/lua/`.

| Path | Responsibility |
| --- | --- |
| `shared/BSCCraft/Rules.lua` | Pure placement rules and request validation |
| `shared/BSCCraft/Base.lua` | Reads the area from Base Stock Counter and the sandbox options |
| `shared/BSCCraft/Guard.lua` | Error containment and throttled logs |
| `client/BSCCraft/Finder.lua` | Nearby lookup and incremental base scan |
| `client/BSCCraft/Hooks.lua` | Shows the containers to crafting only; keeps vanilla transfers away from remote items |
| `client/BSCCraft/Craft.lua` | Fetch before the craft, vanilla container list at start, returns after |
| `client/BSCCraft_Client.lua` | Client events |
| `server/BSCCraft/Service.lua` | Server checks and item moves |
| `server/BSCCraft_Server.lua` | Server and single-player events |

## Development

Use Python 3.13 and the pinned dependency:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests/run.py
.\.venv\Scripts\python.exe tools/check-game.py
~~~

`check-game.py` needs a host JDK and the installed game. It runs the same tests on the game's own Kahlua and checks every Java method the mod calls against the installed jar. Simulated tests don't prove gameplay, sync or performance; see [TESTING.md](docs/TESTING.md).

## License

Copyright (c) 2026 endimonan. All rights reserved.

The source is public to read, learn from and contribute to. It is not open source: reuploads, redistribution, modpack bundling and commercial use require permission. See [LICENSE](LICENSE).
