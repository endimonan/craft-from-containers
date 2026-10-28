# Contributing

Read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [LICENSE](LICENSE) before contributing. The source is public for reading, personal use and contributions under the license; it is not permission to redistribute the mod.

## Bug reports

Include the exact Project Zomboid, Base Stock Counter and mod versions, single-player/hosted/dedicated mode, other enabled mods, steps to reproduce, expected behavior and actual behavior. Add relevant log lines (they start with `[BSCCraftFromContainers]`) and screenshots. Remove passwords, tokens, IP addresses and personal information from logs. Don't upload a whole save unless asked.

## Changes and validation

1. Keep the change focused and follow the existing Lua style. Use `fix/` or `feat/` branch names, same as Base Stock Counter and Item Rarity UI.
2. Add a regression test for a functional bug. Anything touching fetch or return needs a server test (refusals move nothing) and a client test (wait, start, return).
3. Run `python tests/run.py` with the pinned `lupa==2.6`, then `python tools/check-game.py` against the target installation.
4. Test the affected behavior in the actual game. Item movement changes need hosted and dedicated multiplayer runs with two players. Use [TESTING.md](docs/TESTING.md).
5. Review your own diff and open a draft pull request. Describe the problem, the resulting behavior, the exact build and modes tested, automated results and what's still untested. Don't present simulations as gameplay evidence.

## Constraints

- Runtime code is Lua-only. Base Stock Counter is the only dependency, read through `BSCCraft/Base.lua`, never written to.
- Only `server/BSCCraft/Service.lua` moves items, and only after checking every entry with the server's own state. Clients ask; they never move remote items.
- A refused fetch moves nothing. A failed return keeps the item in the inventory, never drops or deletes it.
- Don't wrap `ISHandcraftAction.new`: the server rebuilds actions from its parameter names.
- Keep `getContainers` extended only inside the crafting entry points. Transfers, healing and other callers keep vanilla reach.
- Read loaded chunks only. Don't force-load areas, generate loot or open unexplored containers.
- Persist nothing. No ModData, no item or container modData.
- Contain callback failures and throttle logs. An addon failure must leave vanilla crafting working.

Architecture details are in [ARCHITECTURE.md](docs/ARCHITECTURE.md). Don't add compatibility or save-safety claims without the matching in-game evidence.
