# Architecture

## What the game allows

Read from the installed 42.21.0 jar, not assumed:

- `ISInventoryPaneContextMenu.getContainers(player)` is the list crafting plans with: the inventory plus whatever the loot window shows (the squares around the player). `HandcraftLogic:canPerformCurrentRecipe` has no distance check, so the UI happily shows recipes using any container in that list.
- `BaseCraftingLogic.isContainersAccessible` runs inside `HandcraftLogic.performCurrentRecipe` (and `BuildLogic.performCurrentRecipe`). It refuses the **whole craft** if any container in the list is more than 2.5 squares from the player. In multiplayer this runs on the server.
- `TransactionManager.isConsistent` refuses item transfers between the player and a container more than 5 squares away. In multiplayer a vanilla transfer from the far end of a base is rejected.
- Timed actions with a `complete` method run on the server. The client sends the parameters of `new` (`containers` included) after the Lua `start()` ran, which is why vanilla `ISHandcraftAction:start` has `fixMovedItems`/`fixManualInputs` for items moved into the inventory before the craft.
- `waitToStart` is called every update before an action starts. Cancelling during the wait calls `interruptWaitToStart`, not `stop`.

So extending the container list alone can't work: the craft fails at the last step, and in multiplayer the client can't move far items either. Only server code can.

## The flow

1. **Display.** `Hooks` extends `getContainers` only while the handcraft window refreshes, the item context menu builds its craft options, or a craft is being started. Recipes show as craftable using nearby and base containers.
2. **Start.** The vanilla craft button queues `ISHandcraftAction`s as usual. Inside that scope, `transferIfNeeded` and `ReturnItemsToOriginalContainer` skip remote items: a vanilla transfer from that far would be rejected in multiplayer and cancel the queue.
3. **Fetch.** `ISHandcraftAction.waitToStart` (new method, client and single-player) plans the action's inputs: the player's manual picks, or what a fresh `HandcraftLogic` with the extended list picks right now. Items in remote containers are sent to the server in one `fetch` request. The action waits until the server answers and the items are in the inventory, up to 10 seconds.
4. **Craft.** Before vanilla `start`, the action's `containers` are replaced with the current vanilla list whenever they include a remote container. Vanilla then swaps the moved items in, sends the action to the server, and the server crafts with containers it accepts.
5. **Return.** After `perform`, fetched items still in the inventory (tools, leftovers) are sent back with a `return` request. If the next queued action is another handcraft, they're handed over to it instead, so a batch doesn't move the saw back and forth. `stop` and `interruptWaitToStart` send back whatever was fetched. A fetch answered after a cancel or timeout is sent straight back when it arrives.

`ISHandcraftAction.new` is never wrapped: the server rebuilds actions from the parameter names of `new`.

## Server: the only code that moves items

`Service` runs on the server, and locally in single-player where the client calls it directly. Requests are `fetch` and `return`, each with a request token and up to 200 entries: square coordinates, object index, container index, container type and item ID. `Rules.entries` rejects anything malformed before the world is touched. Each player gets 8 requests per second.

`fetch` is all or nothing. For each entry, with the server's own state:

- the square is loaded and the player may loot it (`SafeHouse.isSafehouseAllowLoot`, the same check vanilla transfers use);
- the square passes `Rules.serverKind`: within vanilla reach, within the nearby radius plus 2 squares on one floor, or in the base area with the player within 2 squares of it;
- the container is found by object and container index, falling back to the first container of the same type holding the item, since object order can differ between client and server;
- the container is explored and not locked to the player, and the item is directly in it (not in a nested bag).

Inventory capacity is not checked. The items only pass through the inventory for the craft, and crafting next to a crate needs no free space in vanilla either.

Only then are the items moved with `ItemContainer:Remove`/`AddItem` and synced with `sendRemoveItemFromContainer`/`sendAddItemToContainer`, the same calls vanilla server code uses. The reply carries `ok` or a code the client shows: `invalid`, `unloaded`, `missing`, `far`, `locked`, `safehouse`, `rate`, `error`. Each refusal is logged once per 30 seconds per code, with the container and item it applies to.

`return` is item by item. An item goes back only if it's still directly in the inventory, not equipped, not a favorite, and the original container passes the same checks and has room. Everything else stays in the inventory. The reply counts what was kept.

Server Lua handles one command at a time, so two players asking for the same item can't both get it.

## Client: which containers

`Finder` builds two lists:

- **Nearby:** squares within the radius on the player's floor, same building as the player (outdoors counts as one). Computed on demand and cached for 500 ms per position.
- **Base:** every explored container in the Base Stock Counter area, all floors, while the player stands in it. Scanned incrementally in `OnTick`, one chunk lookup or one square per step, up to 800 steps or about 2 ms per tick. Chunks come from `getChunkForGridSquare`, levels from `getMinLevel`/`getMaxLevel`, the same way Base Stock Counter scans. A chunk whose `getLoadID` changes mid-scan is dropped from that cycle.

The base scan runs only while crafting was used in the last 30 seconds, every 3 seconds, so an idle base costs nothing. Results are sorted closest first and capped by the sandbox limit. When they change, `ISHandCraftPanel.drawDirty` is set so an open window refreshes.

A container is offered when it's explored, its object isn't a corpse, vehicle, world item or moving object, it isn't locked to the player and its square isn't in a safehouse that excludes the player. Right before it's added, the object must still be on its square (`getObjectIndex() >= 0`).

Unexplored containers are skipped on purpose: `RequestItemsForContainer` makes the server fill an unexplored container with loot.

## Base Stock Counter

`Base` reads the area and never writes to it:

- Server and single-player: `BaseStockCounter.server.engine.data.area`, the authority.
- Multiplayer clients: `BaseStockCounter.client.model.area`, the last committed snapshot.

The bounds are validated again here. If Base Stock Counter is missing or its data looks wrong, base crafting is off and nearby crafting keeps working. `mod.info` has `require=\BaseStockCounter`.

## Persistence and removal

Nothing is persisted. No ModData, no item or container modData, no recipes, items or world objects. Moved items are ordinary items wherever they are. The sandbox options are ignored once the mod is removed.

## Failure handling

Every callback runs through `Guard.call`; errors are logged at most once per 30 seconds per key with the `[BSCCraftFromContainers]` prefix. The scoped `getContainers` wrapper restores its depth before rethrowing, so a vanilla error can't leave the extended reach on. If planning or the container swap throws, vanilla carries on unchanged. If the server throws while handling a request, it answers `error` and nothing else happens. A failing base scan turns the scan off for the session.

## Not covered

- Building and workstation crafting use vanilla reach. Their logic has the same distance check and a different start path.
- The legacy `OnCraft` recipe path is untouched.
- Split-screen: the base scan follows player 1. Other local players get it with their own access checks while player 1 is in the area.
- Performance with hundreds of containers in the crafting window hasn't been measured in game. The base container limit exists for that.
