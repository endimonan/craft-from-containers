-- Server and single-player. Multiplayer clients only send requests.
if isClient() then return end
local G=require "BSCCraft/Guard"
local Base=require "BSCCraft/Base"
local S=require "BSCCraft/Service"
BSCCraftFromContainers=BSCCraftFromContainers or {}
BSCCraftFromContainers.server=S
Events.OnClientCommand.Add(G.call("command",function(module,command,player,args)
    if module=="BSCCraft" then S.command(player,command,args) end
end))
if Events.OnServerStarted then
    Events.OnServerStarted.Add(G.call("check",function()
        if not Base.present() then G.log("dependency","Base Stock Counter is not loaded; base-area crafting is off") end
    end))
end
