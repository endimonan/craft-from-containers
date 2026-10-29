-- Evolved recipes: adding an ingredient to food, like a sandwich, a salad or a stew. The item
-- context menu lists ingredients in nearby and base containers too. A remote ingredient isn't
-- transferred (a transfer from that far is refused in multiplayer); the add action waits for the
-- server to fetch it and sends back what's left of it, the same way crafts do (see Craft).
local G=require "BSCCraft/Guard"
local Hooks=require "BSCCraft/Hooks"
local Craft=require "BSCCraft/Craft"
local K={}

-- Vanilla builds the menu from its own container list, and only offers recipes with an ingredient
-- in it. Both are redone with the extra containers, so ingredients kept only in the base count.
function K.extend(player,baseItem,containerList)
    local character=getSpecificPlayer(player)
    if not character or not baseItem or not containerList then return nil end
    local list=Hooks.extended(character)
    if list:size()<=containerList:size() then return nil end
    return {recipes=RecipeManager.getEvolvedRecipe(baseItem,character,list,true),list=list}
end

function K.menu(original)
    local extend=G.call("cooking menu",K.extend)
    return function(context,items,player,evorecipe,baseItem,containerList,...)
        local extended=not Hooks.disabled and Craft.recipes and extend(player,baseItem,containerList)
        if extended and extended.recipes then evorecipe,containerList=extended.recipes,extended.list end
        return original(context,items,player,evorecipe,baseItem,containerList,...)
    end
end

function K.remote(item,character)
    return Hooks.remote(item:getContainer(),character,Hooks.set(Hooks.vanilla(character)))
end

-- Vanilla's handler, except that a remote ingredient isn't transferred first.
function K.add(original)
    local remote=G.call("cooking add",K.remote)
    return function(recipe,baseItem,usedItem,player,...)
        local character=getSpecificPlayer(player)
        if Hooks.disabled or not Craft.recipes or not character or not usedItem or not baseItem
            or not remote(usedItem,character) then
            return original(recipe,baseItem,usedItem,player,...)
        end
        local inventory=character:getInventory()
        local returnToContainer={}
        if not inventory:contains(baseItem) then
            ISTimedActionQueue.add(ISInventoryTransferUtil.newInventoryTransferAction(character,baseItem,baseItem:getContainer(),inventory,nil))
            table.insert(returnToContainer,baseItem)
            if instanceof(baseItem,"Food") then baseItem:setChef(character:getUsername()) end
        end
        ISTimedActionQueue.add(ISAddItemInRecipe:new(character,recipe,baseItem,usedItem))
        ISCraftingUI.ReturnItemsToOriginalContainer(character,returnToContainer)
    end
end

function K.install()
    if K.installed then return end
    local menu=ISInventoryPaneContextMenu
    if type(menu)~="table" or type(menu.doEvorecipeMenu)~="function" or type(menu.onAddItemInEvoRecipe)~="function"
        or not RecipeManager or not ISInventoryTransferUtil then
        G.log("cooking","Native evolved recipe helpers missing; cooking keeps vanilla reach"); return
    end
    -- Menu options capture the handler when the menu is built, which is after this runs.
    menu.doEvorecipeMenu=K.menu(menu.doEvorecipeMenu)
    menu.onAddItemInEvoRecipe=K.add(menu.onAddItemInEvoRecipe)
    K.installed=true
end

return K
