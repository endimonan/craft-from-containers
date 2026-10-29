time=1000; squares={}; chunks={}; safehouses={}; sent={}; clientSent={}; synced={}; queues={}
SandboxVars={BSCCraft={BaseArea=true,NearbyRadius=5,MaxBaseContainers=256}}
CharacterTrait={DISORGANIZED="Disorganized"}
local seed=42
function testRandom(lo,hi)
    seed=(seed*48271)%2147483647
    return lo+(seed%(hi-lo+1))
end
function getTimestampMs() return time end
function getChunkSizeInSquares() return 8 end
function getText(key) return key end
function isServer() return false end
function isClient() return false end
local classes={IsoThumpable={IsoObject=true},IsoPlayer={IsoGameCharacter=true,IsoMovingObject=true},
    BaseVehicle={IsoMovingObject=true},IsoDeadBody={},IsoWorldInventoryObject={},InventoryItem={},
    Food={InventoryItem=true}}
function instanceof(obj,class)
    if type(obj)~="table" then return false end
    return obj.class==class or (classes[obj.class] or {})[class]==true
end
function print() end

function ArrayList_new(source)
    local l={items={}}
    for i,v in ipairs(source or {}) do l.items[i]=v end
    function l:size() return #self.items end
    function l:get(i) return self.items[i+1] end
    function l:add(v) self.items[#self.items+1]=v end
    return l
end
ArrayList={new=function() return ArrayList_new() end}
function list(items) return ArrayList_new(items) end

function sendServerCommand(player,module,command,args) sent[#sent+1]={player=player,module=module,command=command,args=args} end
function sendClientCommand(player,module,command,args) clientSent[#clientSent+1]={player=player,module=module,command=command,args=args} end
function sendAddItemToContainer(container,item) synced[#synced+1]={"add",container,item} end
function sendRemoveItemFromContainer(container,item) synced[#synced+1]={"remove",container,item} end
function lastClient(command)
    for i=#clientSent,1,-1 do if clientSent[i].command==command then return clientSent[i] end end
end

local function allowed(square,player)
    local rule=safehouses[square.x..":"..square.y]
    return not rule or rule[player]==true
end
SafeHouse={
    getSafeHouse=function(square)
        if not safehouses[square.x..":"..square.y] then return nil end
        return {playerAllowed=function(_,player) return allowed(square,player) end}
    end,
    isSafehouseAllowLoot=function(square,player) return allowed(square,player) end,
}
function safehouse(x,y,members) safehouses[x..":"..y]=members end

ISTimedActionQueue={getTimedActionQueue=function(character)
    queues[character]=queues[character] or {queue={}}
    return queues[character]
end}
function ISTimedActionQueue.add(action)
    local q=ISTimedActionQueue.getTimedActionQueue(action.character)
    q.queue[#q.queue+1]=action
    return action
end

function makeSquare(x,y,z,building)
    local s={x=x,y=y,z=z,building=building,objects={}}
    function s:getX() return self.x end
    function s:getY() return self.y end
    function s:getZ() return self.z end
    function s:getBuilding() return self.building end
    function s:getObjects() return list(self.objects) end
    squares[x..":"..y..":"..z]=s
    local key=math.floor(x/8)..":"..math.floor(y/8)
    chunks[key]=chunks[key] or makeChunk(math.floor(x/8),math.floor(y/8))
    chunks[key].minZ=math.min(chunks[key].minZ,z); chunks[key].maxZ=math.max(chunks[key].maxZ,z)
    return s
end
function makeChunk(cx,cy)
    local c={cx=cx,cy=cy,minZ=0,maxZ=0,id=1}
    function c:getMinLevel() return self.minZ end
    function c:getMaxLevel() return self.maxZ end
    function c:getLoadID() return self.id end
    function c:getGridSquare(x,y,z) return squares[(self.cx*8+x)..":"..(self.cy*8+y)..":"..z] end
    return c
end
function getCell()
    return {
        getGridSquare=function(_,x,y,z) return squares[x..":"..y..":"..z] end,
        getChunkForGridSquare=function(_,x,y,z) return chunks[math.floor(x/8)..":"..math.floor(y/8)] end,
    }
end

local nextId=100
function makeItem(fullType,opts)
    opts=opts or {}
    nextId=nextId+1
    local item={class="InventoryItem",id=opts.id or nextId,fullType=fullType,weight=opts.weight or 1,favorite=opts.favorite}
    function item:getID() return self.id end
    function item:getFullType() return self.fullType end
    function item:getContainer() return self.container end
    function item:isFavorite() return self.favorite==true end
    function item:getUnequippedWeight() return self.weight end
    return item
end
local function holder(c)
    c.items=c.items or {}; c.capacity=c.capacity or 50
    function c:getItems() return list(self.items) end
    function c:containsID(id) return self:getItemWithID(id)~=nil end
    function c:contains(item) for _,it in ipairs(self.items) do if it==item then return true end end return false end
    function c:getItemWithID(id) for _,it in ipairs(self.items) do if it.id==id then return it end end end
    function c:Remove(item)
        for i,it in ipairs(self.items) do if it==item then table.remove(self.items,i); item.container=nil; return end end
    end
    function c:AddItem(item) self.items[#self.items+1]=item; item.container=self; return item end
    function c:load() local w=0; for _,it in ipairs(self.items) do w=w+it.weight end; return w end
    function c:hasRoomFor(player,x) return self:load()+(type(x)=="number" and x or x.weight)<=self.capacity end
    function c:isItemAllowed() return true end
    function c:getType() return self.type end
    return c
end
function put(container,item) container:AddItem(item); return item end

-- A container on a crate standing on the square; returns the container.
function crate(square,opts)
    opts=opts or {}
    local obj={class=opts.class or "IsoObject",square=square,locked=opts.locked}
    local c=holder({explored=opts.explored~=false,parent=obj,name=opts.name,type=opts.type or "crate",capacity=opts.capacity})
    function c:isExplored() return self.explored end
    function c:getParent() return self.parent end
    function c:getOutermostContainer() return self end
    function c:getContainingItem() return nil end
    obj.containers={c}
    function obj:getContainerCount() return #self.containers end
    function obj:getContainerByIndex(i) return self.containers[i+1] end
    function obj:getContainerIndex(container)
        for i,other in ipairs(self.containers) do if other==container then return i-1 end end
        return -1
    end
    function obj:getSquare() return self.square end
    function obj:isLockedToCharacter() return self.locked==true end
    function obj:getObjectIndex()
        if not self.square then return -1 end
        for i,o in ipairs(self.square.objects) do if o==self then return i-1 end end
        return -1
    end
    square.objects[#square.objects+1]=obj
    return c
end
function removeObject(container)
    local obj=container.parent
    for i,o in ipairs(obj.square.objects) do if o==obj then table.remove(obj.square.objects,i) end end
end

function makePlayer(x,y,z,name)
    local p={class="IsoPlayer",x=x,y=y,z=z,name=name or "alice",equipped={},traits={}}
    p.inventory=holder({name="inventory",parent=p,type="none",capacity=50})
    function p.inventory:getOutermostContainer() return self end
    function p.inventory:getParent() return self.parent end
    function p:getX() return self.x+0.5 end
    function p:getY() return self.y+0.5 end
    function p:getZ() return self.z end
    function p:getCurrentSquare() return squares[self.x..":"..self.y..":"..self.z] end
    function p:getInventory() return self.inventory end
    function p:getUsername() return self.name end
    function p:isEquipped(item) return self.equipped[item]==true end
    function p:removeFromHands(item) self.equipped[item]=nil end
    function p:hasTrait(trait) return self.traits[trait]==true end
    function p:setHaloNote(text) self.halo=text end
    return p
end
players={}
function getSpecificPlayer(n) return players[n or 0] end

-- Base Stock Counter as seen by a multiplayer client or by the server engine.
function clientArea(a) BaseStockCounter={client={model={area=a}}} end
function serverArea(a) BaseStockCounter={server={engine={data={area=a}}}} end

-- Vanilla pieces the client hooks wrap. getContainers returns the inventory plus "adjacent".
function vanillaUI(adjacent)
    ISInventoryPaneContextMenu={
        getContainers=function(character)
            local out={character:getInventory()}
            for _,c in ipairs(adjacent or {}) do out[#out+1]=c end
            return list(out)
        end,
        transferIfNeeded=function(player,item) transferred=transferred or {}; transferred[#transferred+1]=item end,
    }
    ISCraftingUI={ReturnItemsToOriginalContainer=function(player,items) givenBack=items end}
end

-- Picks the first matching items across the logic's containers, in list order, like auto inputs.
HandcraftLogic={new=function(player,bench,iso)
    local l={player=player,picked={}}
    function l:setContainers(containers) self.containers=containers end
    function l:setRecipe(recipe) self.recipe=recipe end
    function l:setTargetVariableInputRatio() end
    function l:canPerformCurrentRecipe()
        self.picked={}
        for _,need in ipairs(self.recipe.needs) do
            local n=0
            for i=0,self.containers:size()-1 do
                for _,it in ipairs(self.containers:get(i).items or {}) do
                    if n<need.count and it.fullType==need.type then n=n+1; self.picked[#self.picked+1]=it end
                end
            end
            if n<need.count then return false end
        end
        return true
    end
    function l:getRecipeData()
        local picked=self.picked
        return {getAllInputItems=function() return list(picked) end}
    end
    return l
end}

-- Stand-in for ISHandcraftAction with the methods the mod wraps.
function makeHandcraftClass()
    local Base={}
    Base.__index=Base
    function Base:waitToStart() return false end
    function Base:interruptWaitToStart() self.interrupted=true end
    local A=setmetatable({Type="ISHandcraftAction"},Base)
    A.__index=A
    function A:new(character,recipe,containers,manualInputs,items)
        return setmetatable({character=character,craftRecipe=recipe,containers=containers,
            manualInputs=manualInputs,items=items,variableInputRatio=1},A)
    end
    function A:start() self.startedWith=self.containers; self.started=true end
    function A:perform() self.performed=true; if self.consume then self.consume(self) end end
    function A:complete() self.completed=true; return true end
    function A:stop() self.stopped=true end
    function A:forceStop() self.forced=true; self:stop() end
    return A
end

-- Stand-in for ISAddItemInRecipe. Like vanilla in multiplayer, the start check wants the base item
-- and the ingredient carried.
function makeRecipeActionClass()
    local Base={}
    Base.__index=Base
    function Base:waitToStart() return false end
    function Base:interruptWaitToStart() self.interrupted=true end
    local A=setmetatable({Type="ISAddItemInRecipe"},Base)
    A.__index=A
    function A:new(character,recipe,baseItem,usedItem)
        return setmetatable({character=character,recipe=recipe,baseItem=baseItem,usedItem=usedItem},A)
    end
    function A:isValidStart()
        local inventory=self.character:getInventory()
        return inventory:containsID(self.baseItem:getID()) and inventory:containsID(self.usedItem:getID())
    end
    function A:start() self.started=true; self.startedWith=self.usedItem end
    function A:perform() self.performed=true end
    -- Vanilla uses the ingredient here, after perform().
    function A:complete() self.completed=true; if self.consume then self.consume(self) end; return true end
    function A:stop() self.stopped=true end
    function A:forceStop() self.forced=true; self:stop() end
    return A
end

function food(container,fullType)
    local item=put(container,makeItem(fullType)); item.class="Food"
    function item:setChef(name) self.chef=name end
    return item
end
-- What a multiplayer client gets when the server moves an item to the inventory: the same ID in a
-- new object.
function arrive(player,item)
    item.container:Remove(item)
    local copy=makeItem(item.fullType,{id=item.id}); copy.class=item.class; copy.setChef=item.setChef
    player:getInventory():AddItem(copy)
    return copy
end

function names(entries)
    local out={}
    for _,e in ipairs(entries) do out[#out+1]=e.container.name end
    return table.concat(out,",")
end
function ids(entries)
    local out={}
    for _,e in ipairs(entries) do out[#out+1]=tostring(e.id) end
    return table.concat(out,",")
end
function scanAll(F)
    for i=1,10000 do
        time=time+1
        F.tick()
        if not F.scan then return end
    end
    error("Scan did not finish")
end
-- What the server does after accepting a fetch, as seen by a multiplayer client.
function serverMoves(player,items)
    for _,item in ipairs(items) do item.container:Remove(item); player:getInventory():AddItem(item) end
end
