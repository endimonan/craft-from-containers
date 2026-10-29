-- Ties remote containers into the vanilla handcraft action. The action waits in waitToStart while
-- the server fetches remote inputs into the inventory, starts with the vanilla container list
-- (vanilla refuses any container beyond 2.5 squares when the recipe runs) and sends leftovers back.
local R=require "BSCCraft/Rules"
local G=require "BSCCraft/Guard"
local Hooks=require "BSCCraft/Hooks"
local C={timeout=10000,pending={},serial=0,disabled=false}

function C.id()
    C.serial=C.serial+1
    return tostring(getTimestampMs())..":"..C.serial
end

function C.send(player,command,args)
    if isClient() then sendClientCommand(player,"BSCCraft",command,args); return end
    local server=BSCCraftFromContainers and BSCCraftFromContainers.server
    if server then server.command(player,command,args) end
end

function C.notice(player,key)
    if player then player:setHaloNote(getText(key),255,90,90,300) end
end

function C.entry(item)
    local container=item:getContainer()
    local parent=container:getParent()
    local square=parent:getSquare()
    return {x=square:getX(),y=square:getY(),z=square:getZ(),o=parent:getObjectIndex(),
        c=parent:getContainerIndex(container),t=container:getType(),id=item:getID()}
end

-- Input items the action will use: the player's manual picks, or what the game would pick now
-- with the extra containers included.
function C.inputs(action)
    local out={}
    local function add(list)
        if not list then return end
        for i=0,list:size()-1 do
            local item=list:get(i)
            if item then out[#out+1]=item end
        end
    end
    if action.manualInputs then
        for _,items in pairs(action.manualInputs) do add(items) end
    else
        local logic=HandcraftLogic.new(action.character,action.craftBench,action.isoObject)
        logic:setContainers(Hooks.extended(action.character))
        logic:setRecipe(action.craftRecipe)
        logic:setTargetVariableInputRatio(action.variableInputRatio or 1)
        if logic:canPerformCurrentRecipe() and logic:getRecipeData() then add(logic:getRecipeData():getAllInputItems()) end
    end
    if action.recipeItem then out[#out+1]=action.recipeItem end
    return out
end

function C.plan(action)
    local player=action.character
    local vanilla=Hooks.set(Hooks.vanilla(player))
    local entries,seen={},{}
    for _,item in ipairs(C.inputs(action)) do
        if not seen[item] and Hooks.remote(item:getContainer(),player,vanilla) then
            seen[item]=true
            entries[#entries+1]=C.entry(item)
        end
    end
    return entries
end

function C.arrived(player,entries)
    local inventory=player:getInventory()
    for _,e in ipairs(entries) do
        if not inventory:containsID(e.id) then return false end
    end
    return true
end

function C.fail(s,code)
    s.state="failed"; s.code=code
    C.pending[s.request or ""]=nil
end

-- Called every update until it returns false; the action starts after that.
function C.wait(action)
    local s=action.bscc
    local now=getTimestampMs()
    if not s then
        s={state="ready"}; action.bscc=s
        local entries=C.plan(action)
        if #entries==0 then return false end
        if #entries>R.maxEntries then C.fail(s,"many"); return false end
        s.state="waiting"; s.request=C.id(); s.started=now; s.entries=entries
        C.pending[s.request]=action
        C.send(action.character,"fetch",{request=s.request,items=entries})
    end
    if s.state~="waiting" then return false end
    if s.reply and not s.reply.ok then
        C.fail(s,s.reply.code or "error")
        G.log("fetch "..s.code,"server refused "..#s.entries.." item(s) for "..tostring(action.craftRecipe and action.craftRecipe:getName()))
        return false
    end
    if s.reply and C.arrived(action.character,s.entries) then
        s.state="ready"; s.fetched=s.entries; C.pending[s.request]=nil
        return false
    end
    if now-s.started>=C.timeout then
        s.state="failed"; s.code="timeout"
        if s.reply then
            -- Accepted but not arrived yet: stop() sends back whatever is here by then.
            s.fetched=s.entries; C.pending[s.request]=nil
        else
            -- Still unanswered: a late success is sent straight back by receive().
            s.cancelled=true
        end
        return false
    end
    return true
end

function C.receive(command,args)
    if type(args)~="table" then return end
    if command=="return" then
        if type(args.kept)=="number" and args.kept>0 then C.notice(getSpecificPlayer(0),"IGUI_BSCCraft_Kept") end
        return
    end
    if command~="fetch" then return end
    local action=C.pending[args.request]
    if not action then return end
    local s=action.bscc
    s.reply={ok=args.ok==true,code=args.code}
    if s.cancelled then
        -- The craft was cancelled while waiting: anything that came in goes straight back.
        C.pending[args.request]=nil
        if s.reply.ok then C.giveBack(action.character,s.entries) end
    end
end

-- Before vanilla start: refuse a failed fetch, then let the action take in what was fetched.
function C.prepare(action,adopt)
    local s=action.bscc
    if s and s.state=="failed" then
        local known={invalid=1,unloaded=1,missing=1,far=1,locked=1,safehouse=1,rate=1,timeout=1,many=1}
        C.notice(action.character,"IGUI_BSCCraft_Fetch_"..(known[s.code] and s.code or "error"))
        return false
    end
    return adopt(action)
end

-- Handcraft: drop remote containers from the action. Items fetched for it are in the inventory
-- now; vanilla's fixMovedItems/fixManualInputs swap them in.
function C.adoptCraft(action)
    local player=action.character
    local list=Hooks.vanilla(player)
    local vanilla=Hooks.set(list)
    local containers=action.containers
    if containers then
        for i=0,containers:size()-1 do
            if Hooks.remote(containers:get(i),player,vanilla) then action.containers=list; break end
        end
    end
    if action.recipeItem then
        action.recipeItem=player:getInventory():getItemWithID(action.recipeItem:getID()) or action.recipeItem
    end
    return true
end

function C.records(action)
    local out={}
    for _,source in ipairs({action.bscc and action.bscc.fetched or {}, action.bsccCarry or {}}) do
        for _,e in ipairs(source) do out[#out+1]=e end
    end
    return out
end

-- Fetched items that are still carried go back where they came from (tools, leftovers). Vanilla
-- skips putting things back for disorganized characters, and so does this.
function C.giveBack(player,entries)
    if #entries==0 or player:hasTrait(CharacterTrait.DISORGANIZED) then return end
    local inventory,items=player:getInventory(),{}
    for _,e in ipairs(entries) do
        local item=inventory:getItemWithID(e.id)
        if item and item:getContainer()==inventory then items[#items+1]=e end
    end
    if #items>0 then C.send(player,"return",{request=C.id(),items=items}) end
end

-- At perform the next queued action is still second. A following action of the same kind inherits
-- the fetched items so a batch doesn't send tools back and forth between crafts.
function C.handOver(action)
    local entries=C.records(action)
    if #entries==0 then return nil end
    local queue=ISTimedActionQueue.getTimedActionQueue(action.character)
    local nextAction=queue and queue.queue and queue.queue[2]
    if nextAction and nextAction.Type==action.Type and nextAction.character==action.character then
        nextAction.bsccCarry=nextAction.bsccCarry or {}
        for _,e in ipairs(entries) do table.insert(nextAction.bsccCarry,e) end
        return nil
    end
    return entries
end

-- Methods are replaced on the class. new() is never wrapped: the server rebuilds actions from its
-- parameter names.
function C.hook(A,name,adopt)
    if type(A)~="table" or type(A.start)~="function" or type(A.perform)~="function" or type(A.stop)~="function" then
        G.log("craft "..name,name.." missing; its remote items are display only"); return false
    end
    local waitToStart,interrupt,start,perform,stop=A.waitToStart,A.interruptWaitToStart,A.start,A.perform,A.stop
    local wait=G.call("wait",C.wait)
    local prepare=G.call("prepare",C.prepare)
    local handOver=G.call("hand over",C.handOver)
    local giveBack=G.call("give back",C.giveBack)
    function A.waitToStart(self,...)
        if not C.disabled and wait(self) then return true end
        if waitToStart then return waitToStart(self,...) end
        return false
    end
    function A.start(self,...)
        -- An addon error lets vanilla continue; only a refused fetch stops the craft.
        if not C.disabled and prepare(self,adopt)==false then self:forceStop(); return end
        return start(self,...)
    end
    function A.perform(self,...)
        local entries=handOver(self)
        local result=perform(self,...)
        if entries then giveBack(self.character,entries) end
        return result
    end
    -- Cancelling during waitToStart calls this instead of stop(); a fetch still in flight is sent
    -- back when its reply arrives.
    function A.interruptWaitToStart(self,...)
        local s=self.bscc
        if s and s.state=="waiting" then s.cancelled=true end
        giveBack(self.character,C.records(self))
        if interrupt then return interrupt(self,...) end
    end
    function A.stop(self,...)
        local result=stop(self,...)
        giveBack(self.character,C.records(self))
        return result
    end
    return true
end

function C.install()
    if C.installed then return end
    C.crafts=C.hook(ISHandcraftAction,"ISHandcraftAction",C.adoptCraft)
    C.installed=true
end

return C
