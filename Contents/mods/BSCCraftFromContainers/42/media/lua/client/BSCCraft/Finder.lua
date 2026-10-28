-- Finds extra containers for crafting. Read-only: never fills loot, opens or moves anything.
local R=require "BSCCraft/Rules"
local Base=require "BSCCraft/Base"
local F={budgetMs=2,maxSteps=800,period=3000,interest=30000,nearbyTtl=500,
    result={list={},version=0},nextScan=0,lastUse=-1e12}

function F.excluded(obj)
    return instanceof(obj,"IsoMovingObject") or instanceof(obj,"IsoDeadBody")
        or instanceof(obj,"IsoWorldInventoryObject") or instanceof(obj,"BaseVehicle")
end

-- Unexplored containers have no loot yet; offering them would ask the server to generate it.
function F.usable(container,square,player)
    if not container or not container:isExplored() then return false end
    local parent=container:getParent()
    if instanceof(parent,"IsoThumpable") and parent:isLockedToCharacter(player) then return false end
    local safehouse=SafeHouse and SafeHouse.getSafeHouse(square)
    if safehouse and not safehouse:playerAllowed(player) then return false end
    return true
end

-- The object may have been picked up or destroyed, locally or by another player, since the scan.
function F.alive(container)
    local parent=container and container:getParent()
    return parent~=nil and parent:getSquare()~=nil and parent:getObjectIndex()>=0
end

function F.collect(square,out,player)
    local objects=square:getObjects()
    for i=0,objects:size()-1 do
        local obj=objects:get(i)
        if obj and not F.excluded(obj) then
            for c=0,obj:getContainerCount()-1 do
                local container=obj:getContainerByIndex(c)
                if F.usable(container,square,player) then
                    out[#out+1]={container=container,x=square:getX(),y=square:getY(),z=square:getZ(),i=#out+1}
                end
            end
        end
    end
end

function F.position(player)
    local square=player and player:getCurrentSquare()
    if square then return square:getX(),square:getY(),square:getZ(),square end
end

-- Same floor, same building (or both outdoors): never through walls into a neighbour's house.
function F.nearby(player,o)
    if o.radius<=0 then return {} end
    local px,py,pz,origin=F.position(player)
    if not px then return {} end
    local key=px..":"..py..":"..pz..":"..o.radius
    local now=getTimestampMs()
    local cache=F.nearbyCache
    if cache and cache.player==player and cache.key==key and now-cache.time<F.nearbyTtl then return cache.list end
    local out,cell,building={},getCell(),origin:getBuilding()
    for y=py-o.radius,py+o.radius do
        for x=px-o.radius,px+o.radius do
            local square=cell:getGridSquare(x,y,pz)
            if square and square:getBuilding()==building then F.collect(square,out,player) end
        end
    end
    F.nearbyCache={player=player,key=key,time=now,list=out}
    return out
end

function F.dirty()
    if ISHandCraftPanel then ISHandCraftPanel.drawDirty=true end
end

function F.publish(list,key,player)
    local changed=not R.same(F.result.list,list)
    F.result={list=list,key=key,player=player,version=F.result.version+(changed and 1 or 0)}
    if changed then F.dirty() end
end

function F.clear()
    F.scan=nil
    if #F.result.list>0 then F.publish({},nil,nil) end
end

function F.start(area,key,player,o,now)
    local size=getChunkSizeInSquares()
    F.scan={area=area,key=key,player=player,limit=o.limit,size=size,tiles=R.tiles(area,size),i=1,out={}}
    F.nextScan=now+F.period
end

-- One step is a chunk lookup or a single square, so the tick budget stays predictable.
function F.step(s)
    if not s.chunk then
        local tile=s.tiles[s.i]
        if not tile then return "done" end
        local chunk=getCell():getChunkForGridSquare(tile.cx*s.size,tile.cy*s.size,0)
        if not chunk then s.i=s.i+1; return end
        s.chunk=chunk; s.loadID=chunk:getLoadID(); s.tile=tile
        s.x=tile.x1; s.y=tile.y1; s.z=chunk:getMinLevel(); s.maxZ=chunk:getMaxLevel()
        s.mark=#s.out
        return
    end
    local t=s.tile
    -- A chunk reloaded mid-scan may be another place now; drop what this tile collected.
    if s.chunk:getLoadID()~=s.loadID then
        for i=#s.out,s.mark+1,-1 do s.out[i]=nil end
        s.chunk=nil; s.i=s.i+1; return
    end
    if s.z>s.maxZ then s.chunk=nil; s.i=s.i+1; return end
    local square=s.chunk:getGridSquare(s.x-t.cx*s.size,s.y-t.cy*s.size,s.z)
    if square then F.collect(square,s.out,s.player) end
    s.x=s.x+1
    if s.x>t.x2 then
        s.x=t.x1; s.y=s.y+1
        if s.y>t.y2 then s.y=t.y1; s.z=s.z+1 end
    end
end

function F.finish(s)
    local px,py,pz=F.position(s.player)
    if not px then F.scan=nil; return end
    local inside={}
    for _,e in ipairs(s.out) do
        if R.inside(s.area,e.x,e.y) then inside[#inside+1]=e end
    end
    F.publish(R.nearest(inside,px,py,pz,s.limit),s.key,s.player)
    F.scan=nil
end

function F.tick()
    local player=getSpecificPlayer(0)
    if not player then return end
    local o=Base.options()
    local area=o.base and Base.area()
    local px,py=F.position(player)
    if not area or not px or not R.inside(area,px,py) then F.clear(); return end
    local key=R.key(area)
    if F.result.key and F.result.key~=key then F.clear() end
    if F.scan and F.scan.key~=key then F.scan=nil end
    local now=getTimestampMs()
    if not F.scan then
        -- Idle bases cost nothing: rescan only while crafting was used recently.
        if now<F.nextScan or now-F.lastUse>F.interest then return end
        F.start(area,key,player,o,now)
    end
    local steps=0
    repeat
        if F.step(F.scan)=="done" then F.finish(F.scan); return end
        steps=steps+1
    until steps>=F.maxSteps or getTimestampMs()-now>=F.budgetMs
end

-- Extra containers for this character, closest first. Base entries were filtered for the scanning
-- player; split-screen players get the same checks again.
function F.extra(character)
    local now=getTimestampMs()
    if now-F.lastUse>F.interest then F.nextScan=math.min(F.nextScan,now) end
    F.lastUse=now
    local o=Base.options()
    local out={}
    for _,e in ipairs(F.nearby(character,o)) do out[#out+1]=e end
    local r=F.result
    if #r.list==0 or not o.base then return out end
    local area=Base.area()
    local px,py=F.position(character)
    if not area or R.key(area)~=r.key or not px or not R.inside(area,px,py) then return out end
    local cell=getCell()
    for _,e in ipairs(r.list) do
        local square=r.player~=character and cell:getGridSquare(e.x,e.y,e.z)
        if r.player==character or (square and F.usable(e.container,square,character)) then
            out[#out+1]=e
        end
    end
    return out
end

function F.reset()
    F.result={list={},version=0}; F.scan=nil; F.nextScan=0; F.lastUse=-1e12; F.nearbyCache=nil
end

return F
