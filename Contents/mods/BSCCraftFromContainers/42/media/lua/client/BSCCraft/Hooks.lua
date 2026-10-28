-- Installed from OnGameStart, after every vanilla UI file has loaded.
local Finder=require "BSCCraft/Finder"
local G=require "BSCCraft/Guard"
local H={depth=0,disabled=false}

-- getContainers also backs transfer validation, healing, light sources and other menus. Only the
-- handcraft window, item context crafts and the craft button see the extra containers.
function H.targets()
    return {
        {ISHandCraftPanel,"ISHandCraftPanel","updateContainers"},
        {ISWidgetHandCraftControl,"ISWidgetHandCraftControl","startHandcraft"},
        {ISInventoryPaneContextMenu,"ISInventoryPaneContextMenu","addNewCraftingDynamicalContextMenu"},
        {ISInventoryPaneContextMenu,"ISInventoryPaneContextMenu","OnNewCraft"},
    }
end

-- A container vanilla can't craft from: a world container that isn't carried and isn't in the
-- vanilla list. Items in these are fetched by the server instead of transferred.
function H.remote(container,player,vanilla)
    if not container or vanilla[container] then return false end
    if container:getOutermostContainer()==player:getInventory() then return false end
    local parent=container:getParent()
    return parent~=nil and parent:getSquare()~=nil and not Finder.excluded(parent)
end

function H.set(list)
    local set={}
    for i=0,list:size()-1 do
        local container=list:get(i)
        if container then set[container]=true end
    end
    return set
end

function H.extend(list,character)
    local have=H.set(list)
    local add={}
    for _,e in ipairs(Finder.extra(character)) do
        local container=e.container
        if not have[container] and Finder.alive(container) then have[container]=true; add[#add+1]=container end
    end
    -- Appended only after every check passed, so a failure leaves the vanilla list untouched.
    for _,container in ipairs(add) do list:add(container) end
end

local function pack(...) return {n=select("#",...),...} end

function H.scoped(original)
    return function(...)
        H.depth=H.depth+1
        local result=pack(pcall(original,...))
        H.depth=H.depth-1
        -- The depth must never leak past an error, or every later caller would get the extra reach.
        if not result[1] then error(result[2],0) end
        return unpack(result,2,result.n)
    end
end

-- The list a craft started now would plan with, extra containers included.
function H.extended(player)
    return H.scoped(ISInventoryPaneContextMenu.getContainers)(player)
end

-- The unextended list. Adding to an empty queue starts the action right away, still inside a
-- crafting scope, so callers that need vanilla's view must not go through the wrapper.
function H.vanilla(player)
    return (H.original or ISInventoryPaneContextMenu.getContainers)(player)
end

function H.install()
    if H.installed then return end
    local menu=ISInventoryPaneContextMenu
    if type(menu)~="table" or type(menu.getContainers)~="function" or type(menu.transferIfNeeded)~="function"
        or type(ISCraftingUI)~="table" or type(ISCraftingUI.ReturnItemsToOriginalContainer)~="function" then
        H.disabled=true; G.log("hooks","Native crafting helpers missing"); return
    end
    local getContainers,transferIfNeeded,giveBack=menu.getContainers,menu.transferIfNeeded,ISCraftingUI.ReturnItemsToOriginalContainer
    H.original=getContainers
    local extend=G.call("extend",H.extend,function() H.disabled=true end)
    menu.getContainers=function(character,...)
        local list=getContainers(character,...)
        if H.depth>0 and not H.disabled and list and character then extend(list,character) end
        return list
    end
    -- Inside a craft start, remote items are left to the server fetch: a vanilla transfer from
    -- that far is refused in multiplayer and would cancel the queue.
    local function remoteItem(player,item)
        if H.depth==0 or H.disabled or not instanceof(item,"InventoryItem") then return false end
        return H.remote(item:getContainer(),player,H.set(getContainers(player)))
    end
    local skip=G.call("transfer",remoteItem)
    menu.transferIfNeeded=function(player,item,...)
        if skip(player,item) then return end
        return transferIfNeeded(player,item,...)
    end
    ISCraftingUI.ReturnItemsToOriginalContainer=function(player,items,...)
        local kept={}
        for _,item in ipairs(items or {}) do
            if not skip(player,item) then kept[#kept+1]=item end
        end
        return giveBack(player,kept,...)
    end
    for _,t in ipairs(H.targets()) do
        local class,name,method=t[1],t[2],t[3]
        if type(class)=="table" and type(class[method])=="function" then
            class[method]=H.scoped(class[method])
        else
            G.log("hooks "..name,"Native "..name.."."..method.." missing; that entry point keeps vanilla reach")
        end
    end
    H.installed=true
end

return H
