# In-game tests

Status: automated tests pass on Lua 5.1 and on the game's Kahlua, and every Java method the mod calls exists in 42.21.0. **Nothing below has been run in game yet.** Don't call the mod tested until these pass.

Use disposable saves or copies, never the only copy. Write down the game version, mode (single-player, hosted, dedicated), other mods and logs for every run. Multiplayer runs need at least two players on the same package.

## Single-player

| Scenario | Pass when |
| --- | --- |
| Nearby craft | A plank in a crate 4 squares away, same room. The window shows the recipe; crafting brings the plank, crafts, and a kept tool goes back to its crate |
| Not through walls | Same distance, crate in the next house. It is not offered |
| Base craft | Stand in the Base Stock Counter area, ingredients on another floor. The craft works; leftovers return to their containers |
| Outside the base | Step out of the area. Base containers disappear from the window within a few seconds |
| Batch | Craft 5 with a remote saw. The saw comes once, stays for the batch and goes back after the last one |
| Cancel | Start a craft with remote items and walk away. Whatever came over goes back |
| Manual picks | Pick a specific remote item in the window. That exact item is used |
| Workstation | At a forge or pottery wheel in the base, craft with materials kept in another room. They come over, the craft runs, leftovers go back |
| Cooking | Carry a pot of soup, keep salt in a base cupboard. Right-click the soup: adding salt is offered. Adding it brings the salt, and what's left goes back to the cupboard |
| Cooking, used up | Add an ingredient that is used up completely. Nothing goes back and nothing is duplicated |
| Cooking, base item nearby | The soup sits on the stove next to you, the salt is in the base. The pot moves the vanilla way, the salt through the server |
| Disorganized | Leftovers stay in the inventory, like vanilla |
| Unexplored, locked | A never-opened crate and a locked one in the base are never offered |
| Removal | Disable the mod, load the save. Inventories and containers are as they were; crafting is vanilla again |

## Multiplayer (hosted and dedicated)

| Scenario | Pass when |
| --- | --- |
| Sync | A crafts with items from a base crate while B watches that crate. B sees the items leave and the leftovers come back, without reopening anything |
| Cooking sync | A salts a stew from a base cupboard while B watches the cupboard. The salt leaves, the stew gets it, what's left comes back |
| Same item | A and B start crafts needing the only plank in a crate at the same time. One succeeds, the other is cancelled with a message. No duplicate plank, no lost plank |
| Server reach | Change the area on the server while a client still has the old one cached, then craft from a container outside the new area. The server refuses with a message and nothing moves |
| Lag | With simulated latency, crafts still finish. The 10-second wait isn't hit under normal latency |
| Safehouse | A container in someone else's safehouse is never used, even in the base area |
| Full inventory | Fill the inventory, then craft something heavy from the base. The items still come over for the craft and go back after |
| Full container | Fill the source container after fetching. The tool stays in the inventory with a message |
| Tool timing | Craft with a remote tool. The craft completes before the tool goes back (the client waits for the server to finish the action) |
| Restart | Restart the server mid-batch. Nothing is lost; items are in the inventory or the containers |

## Performance

Base of 100 x 100 with four levels and about 200 containers. Open the crafting window inside the base and record frame time while it refreshes, plus the time from opening to base recipes showing. Lower the base container limit and compare. Also record server time for a fetch of 50 items.

Simulated tests only cover logic. Report what was actually run and what wasn't.
