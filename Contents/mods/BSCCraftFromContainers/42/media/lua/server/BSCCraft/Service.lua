-- The only code in the mod that moves items. Runs on the server, and locally in single-player.
-- Vanilla refuses crafting with containers beyond 2.5 squares and transfers beyond 5, so remote
-- items reach the inventory here, under the server's own checks, before the vanilla craft starts.
local R=require "BSCCraft/Rules"
local Base=require "BSCCraft/Base"
local G=require "BSCCraft/Guard"
local S={limits=setmetatable({},{__mode="k"}),window=1000,perWindow=8}

function S.excluded(obj)
    return instanceof(obj,"IsoMovingObject") or instanceof(obj,"IsoDeadBody")
        or instanceof(obj,"IsoWorldInventoryObject") or instanceof(obj,"BaseVehicle")
end

local function at(square,o,c)
    local objects=square:getObjects()
    if o>=objects:size() then return nil end
    local obj=objects:get(o)
    if not obj or S.excluded(obj) or c>=obj:getContainerCount() then return nil end
    return obj,obj:getContainerByIndex(c)
end

-- The container the client named. Object order can differ between client and server, so a
-- mismatch falls back to the first container of the same type on that square.
function S.locate(square,e,holding)
    local obj,container=at(square,e.o,e.c)
    if container and container:getType()==e.t and (not holding or container:containsID(e.id)) then return obj,container end
    local objects=square:getObjects()
    for i=0,objects:size()-1 do
        local candidate=objects:get(i)
        if candidate and not S.excluded(candidate) then
            for c=0,candidate:getContainerCount()-1 do
                local other=candidate:getContainerByIndex(c)
                if other and other:getType()==e.t and (not holding or other:containsID(e.id)) then return candidate,other end
            end
        end
    end
end

-- Same rules as the client, with the server's own position, area and safehouse state.
function S.reach(player,e,o,area)
    local square=getCell():getGridSquare(e.x,e.y,e.z)
    if not square then return nil,"unloaded" end
    if not R.serverKind(o,math.floor(player:getX()),math.floor(player:getY()),math.floor(player:getZ()),e.x,e.y,e.z,area) then
        return nil,"far"
    end
    if not SafeHouse.isSafehouseAllowLoot(square,player) then return nil,"safehouse" end
    return square
end

function S.usable(obj,container,player)
    if not container:isExplored() then return "missing" end
    if instanceof(obj,"IsoThumpable") and obj:isLockedToCharacter(player) then return "locked" end
end

function S.move(item,from,to)
    from:Remove(item)
    if isServer() then sendRemoveItemFromContainer(from,item) end
    to:AddItem(item)
    if isServer() then sendAddItemToContainer(to,item) end
end

-- All or nothing: every entry is checked before the first item moves. Capacity is not checked:
-- the items only pass through the inventory for the craft, like crafting next to a crate needs no
-- free space in vanilla. Returns the refusal code and the entry it applies to.
function S.fetch(player,a)
    local entries=R.entries(a.items)
    if not entries then return "invalid" end
    local o,area=Base.options(),Base.area()
    local inventory=player:getInventory()
    local moves={}
    for _,e in ipairs(entries) do
        local square,code=S.reach(player,e,o,area)
        if not square then return code,e end
        local obj,container=S.locate(square,e,true)
        if not container then return "missing",e end
        code=S.usable(obj,container,player)
        if code then return code,e end
        local item=container:getItemWithID(e.id)
        if not item or item:getContainer()~=container then return "missing",e end
        moves[#moves+1]={item=item,from=container}
    end
    for _,m in ipairs(moves) do S.move(m.item,m.from,inventory) end
end

function S.describe(player,code,e)
    local where=e and (" "..e.t.." at "..e.x..","..e.y..","..e.z.." item "..e.id) or ""
    return tostring(player:getUsername()).." refused "..code..where
end

-- Best effort, item by item: anything that can't go back stays in the inventory.
function S.giveBack(player,a)
    local entries=R.entries(a.items)
    if not entries then return 0,0 end
    local o,area=Base.options(),Base.area()
    local inventory=player:getInventory()
    local returned,kept=0,0
    for _,e in ipairs(entries) do
        local item=inventory:getItemWithID(e.id)
        local square=item and item:getContainer()==inventory and not item:isFavorite()
            and not player:isEquipped(item) and S.reach(player,e,o,area)
        local obj,container
        if square then obj,container=S.locate(square,e,false) end
        if container and not S.usable(obj,container,player) and container:isItemAllowed(item) and container:hasRoomFor(player,item) then
            S.move(item,inventory,container); returned=returned+1
        elseif item then
            kept=kept+1
        end
    end
    return returned,kept
end

function S.reply(player,command,args)
    if isServer() then sendServerCommand(player,"BSCCraft",command,args)
    else
        local client=BSCCraftFromContainers and BSCCraftFromContainers.client
        if client then client.receive(command,args) end
    end
end

function S.command(player,command,a)
    if not player or type(a)~="table" or not R.token(a.request) then return end
    if command~="fetch" and command~="return" then return end
    -- Identity comes from OnClientCommand; the limit keeps a client from spamming world lookups.
    local now=getTimestampMs()
    local rate=S.limits[player]
    if not rate or now-rate.start>=S.window then rate={start=now,count=0}; S.limits[player]=rate end
    rate.count=rate.count+1
    if command=="fetch" then
        local ok,code,entry=true,"rate",nil
        if rate.count<=S.perWindow then ok,code,entry=pcall(S.fetch,player,a) end
        if not ok then G.log("fetch",code); code="error" end
        -- Throttled per code, so a refused batch leaves one line explaining it.
        if code then G.log("refused "..code,S.describe(player,code,entry)) end
        S.reply(player,"fetch",{request=a.request,ok=code==nil,code=code})
    else
        local ok,returned,kept=true,0,1
        if rate.count<=S.perWindow then ok,returned,kept=pcall(S.giveBack,player,a) end
        if not ok then G.log("return",returned); returned,kept=0,1 end
        S.reply(player,"return",{request=a.request,returned=returned,kept=kept})
    end
end

return S
