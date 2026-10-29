local G=require "BSCCraft/Guard"
local Base=require "BSCCraft/Base"
local Finder=require "BSCCraft/Finder"
local Hooks=require "BSCCraft/Hooks"
local Craft=require "BSCCraft/Craft"
local Cooking=require "BSCCraft/Cooking"
BSCCraftFromContainers=BSCCraftFromContainers or {}
BSCCraftFromContainers.client=Craft

Events.OnGameStart.Add(G.call("start",function()
    Finder.reset(); Finder.disabled=false; Craft.pending={}
    if not Base.present() then G.log("dependency","Base Stock Counter is not loaded; base-area crafting is off") end
    Hooks.install()
    Craft.install()
    Cooking.install()
end))
Events.OnTick.Add(G.call("tick",function() if not Finder.disabled then Finder.tick() end end,
    function() Finder.reset(); Finder.disabled=true end))
Events.OnServerCommand.Add(G.call("server command",function(module,command,args)
    if module=="BSCCraft" then Craft.receive(command,args) end
end))
if Events.OnDisconnect then
    Events.OnDisconnect.Add(G.call("disconnect",function() Finder.reset(); Craft.pending={} end))
end
