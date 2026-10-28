-- Read-only adapter to Base Stock Counter and the sandbox options. Nothing here is persisted.
local R=require "BSCCraft/Rules"
local B={}

function B.present()
    return type(BaseStockCounter)=="table"
end

-- The server engine is the authority where it runs (dedicated server, host and single-player).
-- Multiplayer clients only have the area from their last committed snapshot.
function B.area()
    local bsc=BaseStockCounter
    if type(bsc)~="table" then return nil end
    local engine=type(bsc.server)=="table" and bsc.server.engine
    if type(engine)=="table" and type(engine.data)=="table" then return R.area(engine.data.area) end
    local model=type(bsc.client)=="table" and bsc.client.model
    if type(model)=="table" then return R.area(model.area) end
    return nil
end

function B.options()
    return R.options(type(SandboxVars)=="table" and SandboxVars.BSCCraft or nil)
end

return B
