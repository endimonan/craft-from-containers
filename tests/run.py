"""Host-native Lua 5.1 tests; no game installation or save is touched."""
from pathlib import Path
import json
import re
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "Contents/mods/BSCCraftFromContainers/42"
LUA = MOD / "media/lua"


class ModTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        paths = ";".join((LUA / side / "?.lua").as_posix() for side in ("shared", "server", "client"))
        self.lua.globals().test_path = paths
        self.lua.execute("package.path = test_path .. ';' .. package.path")
        self.lua.execute((ROOT / "tests/fixtures.lua").read_text(encoding="utf-8"))

    def check(self, code):
        self.lua.execute(code)

    def test_lua51_syntax_and_translations(self):
        for path in LUA.rglob("*.lua"):
            self.lua.globals().source = path.read_text(encoding="utf-8")
            self.check("assert(loadstring(source))")
        for name in ("IG_UI", "Sandbox"):
            en, pt = (json.loads((LUA / f"shared/Translate/{lang}/{name}.json").read_text(encoding="utf-8")) for lang in ("EN", "PTBR"))
            self.assertEqual(en.keys(), pt.keys())
            for key in en:
                self.assertEqual(re.findall(r"%\d", en[key]), re.findall(r"%\d", pt[key]))
        used = set()
        for path in LUA.rglob("*.lua"):
            used.update(re.findall(r'"(IGUI_BSCCraft_\w+)"', path.read_text(encoding="utf-8")))
        ui = json.loads((LUA / "shared/Translate/EN/IG_UI.json").read_text(encoding="utf-8"))
        self.assertIn("IGUI_BSCCraft_Fetch_", used)
        self.assertTrue(used - {"IGUI_BSCCraft_Fetch_"} <= ui.keys())
        craft = (LUA / "client/BSCCraft/Craft.lua").read_text(encoding="utf-8")
        codes = re.search(r"local known=\{([^}]*)\}", craft).group(1)
        for code in re.findall(r"(\w+)=1", codes) + ["error"]:
            self.assertIn(f"IGUI_BSCCraft_Fetch_{code}", ui)
        options = (MOD / "media/sandbox-options.txt").read_text(encoding="utf-8")
        sandbox = json.loads((LUA / "shared/Translate/EN/Sandbox.json").read_text(encoding="utf-8"))
        for page in set(re.findall(r"page = (\w+)", options)):
            self.assertIn(f"Sandbox_{page}", sandbox)
        for name in re.findall(r"translation = (\w+)", options):
            self.assertIn(f"Sandbox_{name}", sandbox)
            self.assertIn(f"Sandbox_{name}_tooltip", sandbox)
        info = (MOD / "mod.info").read_text(encoding="utf-8")
        self.assertIn("require=\\BaseStockCounter", info.splitlines())

    def test_rules_area_options_and_tiles(self):
        self.check('''
            local R=require "BSCCraft/Rules"
            assert(R.area({x1=10,y1=10,x2=109,y2=109}).x2==109)
            for _,bad in ipairs({-1,0/0,math.huge,1.5,"1"}) do
                assert(not R.area({x1=bad,y1=0,x2=1,y2=1}))
            end
            assert(not R.area({x1=5,y1=0,x2=4,y2=1}))
            assert(not R.area({x1=0,y1=0,x2=256,y2=0}))
            assert(not R.area(nil) and not R.area("area"))
            local o=R.options(nil)
            assert(o.base and o.radius==5 and o.limit==256)
            o=R.options({BaseArea=false,NearbyRadius=99,MaxBaseContainers=1})
            assert(not o.base and o.radius==15 and o.limit==16)
            o=R.options({NearbyRadius=-4.7,MaxBaseContainers=1e9})
            assert(o.radius==0 and o.limit==1024)
            for trial=1,100 do
                local x,y=testRandom(0,200),testRandom(0,200)
                local w,h=testRandom(1,100),testRandom(1,100)
                local a=R.area({x1=x,y1=y,x2=x+w-1,y2=y+h-1})
                local seen,n={},0
                for _,t in ipairs(R.tiles(a,8)) do
                    for tx=t.x1,t.x2 do for ty=t.y1,t.y2 do
                        local key=tx..":"..ty
                        assert(not seen[key]); seen[key]=true; n=n+1
                        assert(math.floor(tx/8)==t.cx and math.floor(ty/8)==t.cy)
                    end end
                end
                assert(n==w*h)
            end
        ''')

    def test_rules_client_offers_only_what_the_server_accepts(self):
        self.check('''
            local R=require "BSCCraft/Rules"
            local a={x1=10,y1=10,x2=29,y2=29}
            local o=R.options({NearbyRadius=4})
            assert(R.clientKind(o,15,15,0,28,28,2,a)=="base")
            assert(R.clientKind(o,9,15,0,12,15,0,a)=="nearby")
            assert(R.clientKind(o,9,15,0,28,28,0,a)==nil)
            assert(R.clientKind(o,15,15,0,40,15,0,a)==nil)
            assert(R.clientKind(o,15,15,0,15,18,1,nil)==nil)
            assert(R.clientKind(R.options({BaseArea=false,NearbyRadius=0}),15,15,0,16,15,0,a)==nil)
            assert(R.serverKind(o,15,15,0,20,15,1,nil)=="reach")
            assert(R.serverKind(o,15,15,0,21,15,0,nil)=="nearby")
            assert(R.serverKind(o,15,15,0,22,15,0,nil)==nil)
            assert(R.serverKind(o,8,15,0,28,28,3,a)=="base")
            assert(R.serverKind(o,7,15,0,28,28,3,a)==nil)
            assert(R.serverKind(o,15,15,0,28,30,0,a)==nil)
            assert(R.serverKind(R.options({BaseArea=false}),15,15,0,28,28,0,a)==nil)
            -- Anything the client offers must survive the server check, even after a short move.
            for trial=1,3000 do
                local opts=R.options({BaseArea=testRandom(0,1)==1,NearbyRadius=testRandom(0,15)})
                local px,py,pz=testRandom(0,40),testRandom(0,40),testRandom(0,2)
                local tx,ty,tz=testRandom(0,40),testRandom(0,40),testRandom(0,2)
                if R.clientKind(opts,px,py,pz,tx,ty,tz,a) then
                    local mx,my=px+testRandom(-2,2),py+testRandom(-2,2)
                    assert(R.serverKind(opts,mx,my,pz,tx,ty,tz,a),"server refused a client offer")
                end
            end
            local entries={{x=5,y=5,z=0,i=1},{x=1,y=1,z=0,i=2},{x=2,y=1,z=1,i=3},{x=1,y=1,z=0,i=4}}
            local near=R.nearest(entries,1,1,0,3)
            assert(#near==3 and near[1].i==2 and near[2].i==4 and near[3].i==3)
        ''')

    def test_finder_scans_the_base_with_access_rules(self):
        self.check('''
            local F=require "BSCCraft/Finder"
            SandboxVars.BSCCraft.NearbyRadius=0
            ISHandCraftPanel={}
            local area={x1=0,y1=0,x2=19,y2=19}
            clientArea(area)
            local p=makePlayer(5,5,0); players[0]=p; makeSquare(5,5,0,"home")
            crate(makeSquare(6,5,0,"home"),{name="near"})
            crate(makeSquare(18,18,1,"home"),{name="attic"})
            crate(makeSquare(19,3,-1,"home"),{name="basement"})
            crate(makeSquare(25,25,0,"home"),{name="outside"})
            crate(makeSquare(10,10,0,"home"),{name="unexplored",explored=false})
            crate(makeSquare(11,10,0,"home"),{name="locked",class="IsoThumpable",locked=true})
            crate(makeSquare(11,11,0,"home"),{name="unlocked",class="IsoThumpable"})
            local denied=makeSquare(12,12,0,"home"); crate(denied,{name="denied"}); safehouse(12,12,{})
            local member=makeSquare(13,12,0,"home"); crate(member,{name="member"}); safehouse(13,12,{[p]=true})
            crate(makeSquare(14,14,0,"home"),{name="corpse",class="IsoDeadBody"})
            crate(makeSquare(15,14,0,"home"),{name="car",class="BaseVehicle"})
            -- Nothing is scanned until crafting asks for containers.
            for i=1,50 do time=time+100; F.tick() end
            assert(not F.scan and #F.result.list==0)
            assert(#F.extra(p)==0)
            scanAll(F)
            assert(names(F.result.list)=="near,unlocked,member,attic,basement","got "..names(F.result.list))
            assert(ISHandCraftPanel.drawDirty)
            assert(names(F.extra(p))=="near,unlocked,member,attic,basement")
            -- An unchanged rescan does not dirty the crafting UI again.
            ISHandCraftPanel.drawDirty=false
            time=time+3000; scanAll(F)
            assert(not ISHandCraftPanel.drawDirty)
            -- A second local player gets the access checks again.
            local guest=makePlayer(6,6,0,"guest"); makeSquare(6,6,0,"home")
            assert(names(F.extra(guest))=="near,unlocked,attic,basement")
            -- Leaving the area drops the base list.
            makeSquare(30,30,0); p.x=30; p.y=30
            F.tick()
            assert(#F.result.list==0 and #F.extra(p)==0)
        ''')

    def test_finder_limit_reloads_and_missing_dependency(self):
        self.check('''
            local F=require "BSCCraft/Finder"
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=0,MaxBaseContainers=16}
            local area={x1=0,y1=0,x2=19,y2=19}
            serverArea(area)
            local p=makePlayer(0,0,0); players[0]=p; makeSquare(0,0,0)
            for i=1,19 do crate(makeSquare(i,i,0),{name="c"..i}) end
            F.extra(p); scanAll(F)
            assert(#F.result.list==16 and F.result.list[1].container.name=="c1" and F.result.list[16].container.name=="c16")
            -- A chunk reloaded mid-scan may be another place: its tile is dropped, not mixed in.
            F.reset(); F.maxSteps=10; F.extra(p)
            local s
            repeat time=time+1; F.tick(); s=F.scan until not s or (s.chunk and s.tile.cx==1 and s.tile.cy==1 and s.mark>0 and #s.out>s.mark)
            assert(s, "scan never reached the reloading tile")
            chunks["1:1"].id=2
            scanAll(F)
            for _,e in ipairs(F.result.list) do assert(not (e.x>=8 and e.x<=15 and e.y>=8 and e.y<=15)) end
            chunks["1:1"].id=1
            -- Turning the option off or losing Base Stock Counter disables base crafting quietly.
            SandboxVars.BSCCraft.BaseArea=false; F.tick()
            assert(#F.result.list==0 and #F.extra(p)==0)
            SandboxVars.BSCCraft.BaseArea=true; BaseStockCounter=nil; F.tick()
            assert(#F.extra(p)==0)
            BaseStockCounter={client={model={area={x1=0,y1=0,x2=999,y2=0}}}}
            F.tick(); assert(#F.extra(p)==0)
        ''')

    def test_finder_nearby_same_floor_same_building(self):
        self.check('''
            local F=require "BSCCraft/Finder"
            SandboxVars.BSCCraft={BaseArea=false,NearbyRadius=2}
            local p=makePlayer(50,50,0); players[0]=p; makeSquare(50,50,0,"home")
            crate(makeSquare(52,51,0,"home"),{name="shelf"})
            crate(makeSquare(49,50,0,"home"),{name="fridge"})
            crate(makeSquare(53,50,0,"home"),{name="far"})
            crate(makeSquare(51,50,1,"home"),{name="upstairs"})
            crate(makeSquare(50,52,0,"neighbour"),{name="neighbour"})
            crate(makeSquare(51,48,0),{name="yard"})
            assert(names(F.extra(p))=="fridge,shelf","got "..names(F.extra(p)))
            -- Cached briefly per position: world changes show up after the TTL.
            crate(makeSquare(50,51,0,"home"),{name="new"})
            assert(names(F.extra(p))=="fridge,shelf")
            time=time+600
            assert(names(F.extra(p))=="fridge,new,shelf")
            SandboxVars.BSCCraft.NearbyRadius=0
            assert(#F.extra(p)==0)
        ''')

    def test_hooks_extend_only_inside_crafting_entry_points(self):
        self.check('''
            local F=require "BSCCraft/Finder"
            local H=require "BSCCraft/Hooks"
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=0}
            clientArea({x1=0,y1=0,x2=9,y2=9})
            local p=makePlayer(1,1,0); players[0]=p; makeSquare(1,1,0)
            local own=crate(makeSquare(2,1,0),{name="adjacent"})
            local far=crate(makeSquare(9,9,0),{name="far"})
            local gone=crate(makeSquare(8,9,0),{name="gone"})
            vanillaUI({own})
            ISHandCraftPanel={updateContainers=function(self)
                self.seen=ISInventoryPaneContextMenu.getContainers(p)
                return "a",nil,"c"
            end}
            local native=function(self) error("native failure") end
            local remoteItem=put(far,makeItem("Base.Plank"))
            local nearItem=put(own,makeItem("Base.Plank"))
            ISWidgetHandCraftControl={startHandcraft=function(self,fail)
                ISInventoryPaneContextMenu.transferIfNeeded(p,remoteItem)
                ISInventoryPaneContextMenu.transferIfNeeded(p,nearItem)
                ISCraftingUI.ReturnItemsToOriginalContainer(p,{remoteItem,nearItem})
                if fail then native(self) end
            end}
            local original=ISWidgetHandCraftControl.startHandcraft
            H.install(); H.install()
            local panel={}
            ISHandCraftPanel.updateContainers(panel)
            scanAll(F)
            removeObject(gone)
            local a,b,c=ISHandCraftPanel.updateContainers(panel)
            assert(a=="a" and b==nil and c=="c")
            assert(select("#",ISHandCraftPanel.updateContainers(panel))==3)
            assert(panel.seen:size()==3 and panel.seen:get(0)==p:getInventory() and panel.seen:get(1)==own and panel.seen:get(2)==far)
            -- Transfers, healing and every other caller keep vanilla reach.
            assert(ISInventoryPaneContextMenu.getContainers(p):size()==2)
            -- Inside a craft start, remote items are left to the server fetch; adjacent ones stay vanilla.
            transferred=nil; givenBack=nil
            ISWidgetHandCraftControl.startHandcraft({})
            assert(#transferred==1 and transferred[1]==nearItem)
            assert(#givenBack==1 and givenBack[1]==nearItem)
            transferred=nil
            ISInventoryPaneContextMenu.transferIfNeeded(p,remoteItem)
            assert(#transferred==1 and transferred[1]==remoteItem)
            -- A native error propagates unchanged and the scope cannot leak.
            -- Compared with the unwrapped error: Kahlua's test platform words some messages differently.
            local _,expected=pcall(original,{},true)
            local ok,err=pcall(ISWidgetHandCraftControl.startHandcraft,{},true)
            assert(not ok and err==expected and H.depth==0)
            assert(ISInventoryPaneContextMenu.getContainers(p):size()==2)
            -- An addon failure returns the vanilla list and turns the extension off.
            F.extra=function() error("addon failure") end
            ISHandCraftPanel.updateContainers(panel)
            assert(panel.seen:size()==2 and H.disabled)
        ''')

    def test_rules_entries_reject_malformed_requests(self):
        self.check('''
            local R=require "BSCCraft/Rules"
            local good={x=10,y=12,z=-1,o=2,c=0,t="crate",id=-7}
            local out=R.entries({good,{x=1,y=1,z=0,o=0,c=1,t="fridge",id=9}})
            assert(#out==2 and out[1].id==-7 and out[2].t=="fridge")
            local function bad(change)
                local e={x=10,y=12,z=0,o=2,c=0,t="crate",id=5}
                for k,v in pairs(change) do e[k]=v end
                return R.entries({e})==nil
            end
            assert(bad({x=1.5}) and bad({y=-1}) and bad({z=99}) and bad({o=-1}) and bad({c="0"}) and bad({id=0/0}))
            assert(bad({t=""}) and bad({t=string.rep("a",65)}) and bad({t="crate\\n"}) and bad({t=5}))
            assert(R.entries({good,good})==nil)
            assert(R.entries({})==nil and R.entries("x")==nil and R.entries({"x"})==nil)
            local many={}
            for i=1,R.maxEntries do many[i]={x=1,y=1,z=0,o=0,c=0,t="crate",id=i} end
            assert(#R.entries(many)==R.maxEntries)
            many[#many+1]={x=1,y=1,z=0,o=0,c=0,t="crate",id=0}
            assert(R.entries(many)==nil)
            assert(R.token("abc") and not R.token("") and not R.token(string.rep("a",65)) and not R.token(5))
        ''')

    def test_service_fetch_checks_everything_before_moving(self):
        self.check('''
            isServer=function() return true end
            local S=require "BSCCraft/Service"
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=4}
            serverArea({x1=0,y1=0,x2=19,y2=19})
            local p=makePlayer(5,5,0)
            local attic=crate(makeSquare(18,18,1),{name="attic"})
            local wood=put(attic,makeItem("Base.Plank",{weight=2}))
            local saw=put(attic,makeItem("Base.Saw",{weight=1}))
            local function entry(container,item,o,c,t)
                local obj=container.parent
                return {x=obj.square.x,y=obj.square.y,z=obj.square.z,o=o or obj:getObjectIndex(),
                    c=c or obj:getContainerIndex(container),t=t or container.type,id=item.id}
            end
            local n=0
            local function fetch(items,player)
                n=n+1; time=time+200; sent={}; synced={}
                S.command(player or p,"fetch",{request="r"..n,items=items})
                assert(#sent==1 and sent[1].command=="fetch" and sent[1].args.request=="r"..n)
                return sent[1].args
            end
            -- Every refusal leaves both items where they were.
            local outside=crate(makeSquare(40,40,0),{name="outside"})
            local stray=put(outside,makeItem("Base.Nails"))
            local cold=crate(makeSquare(17,18,1),{name="cold",explored=false})
            local hidden=put(cold,makeItem("Base.Nails"))
            local shut=crate(makeSquare(16,18,1),{name="shut",class="IsoThumpable",locked=true})
            local kept=put(shut,makeItem("Base.Nails"))
            local claimed=crate(makeSquare(15,18,1),{name="claimed"}); safehouse(15,18,{})
            local theirs=put(claimed,makeItem("Base.Nails"))
            local cases={
                {entry(outside,stray),"far"},{entry(cold,hidden),"missing"},{entry(shut,kept),"locked"},
                {entry(claimed,theirs),"safehouse"},{entry(attic,makeItem("Base.Ghost")),"missing"},
                {{x=30,y=3,z=0,o=0,c=0,t="crate",id=1},"unloaded"},
            }
            for _,case in ipairs(cases) do
                local reply=fetch({entry(attic,wood),case[1]})
                assert(not reply.ok and reply.code==case[2],tostring(reply.code).." for "..case[2])
                assert(wood.container==attic and #p.inventory.items==0 and #synced==0)
            end
            assert(fetch({{x=1}}).code=="invalid")
            -- Only items directly in the container: a lookup that finds one inside a nested bag is refused.
            local bagged=put(crate(makeSquare(14,18,1),{name="bag"}),makeItem("Base.Nails"))
            local pack=bagged.container
            local holderOf=crate(makeSquare(13,18,1),{name="pack"})
            holderOf.getItemWithID=function() return bagged end
            holderOf.containsID=function() return true end
            assert(fetch({entry(holderOf,bagged)}).code=="missing" and bagged.container==pack)
            -- Two squares of slack outside the area cover lag; three are refused. Stale indexes fall
            -- back to the container of the same type holding the item.
            -- A full inventory doesn't block it: the items only pass through for the craft.
            p.x=-2; p.inventory.capacity=0
            local reply=fetch({entry(attic,wood,7,3,"crate"),entry(attic,saw)})
            assert(reply.ok and wood.container==p.inventory and saw.container==p.inventory)
            assert(#synced==4 and synced[1][1]=="remove" and synced[1][2]==attic and synced[2][1]=="add" and synced[2][2]==p.inventory)
            p.inventory:Remove(wood); attic:AddItem(wood); p.inventory.capacity=50
            p.x=-3
            assert(fetch({entry(attic,wood)}).code=="far")
            -- Without the base option or Base Stock Counter, only the nearby radius is left.
            p.x=5; SandboxVars.BSCCraft.BaseArea=false
            assert(fetch({entry(attic,wood)}).code=="far")
            SandboxVars.BSCCraft.BaseArea=true; BaseStockCounter=nil
            assert(fetch({entry(attic,wood)}).code=="far")
            local shelf=crate(makeSquare(5,11,0),{name="shelf",type="shelves"})
            local nails=put(shelf,makeItem("Base.Nails"))
            assert(fetch({entry(shelf,nails)}).ok and nails.container==p.inventory)
            -- Rate limit per player, per second.
            local q=makePlayer(5,5,0,"bob")
            for i=1,S.perWindow do sent={}; S.command(q,"fetch",{request="q"..i,items={{x=1}}}) end
            sent={}; S.command(q,"fetch",{request="flood",items={{x=1}}})
            assert(sent[1].args.code=="rate")
            -- Malformed requests get no reply at all.
            sent={}; S.command(p,"fetch",{request=5}); S.command(p,"steal",{request="x"}); S.command(p,"fetch","x")
            assert(#sent==0)
        ''')

    def test_service_gives_back_what_it_can(self):
        self.check('''
            isServer=function() return true end
            local S=require "BSCCraft/Service"
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=0}
            serverArea({x1=0,y1=0,x2=19,y2=19})
            local p=makePlayer(5,5,0)
            local spot=makeSquare(12,12,0)
            local shelf=crate(spot,{name="shelf",type="shelves",capacity=3})
            local other=crate(spot,{name="other",type="crate"})
            local saw=put(p.inventory,makeItem("Base.Saw"))
            local hammer=put(p.inventory,makeItem("Base.Hammer"))
            local fav=put(p.inventory,makeItem("Base.Axe",{favorite=true}))
            local held=put(p.inventory,makeItem("Base.Knife")); p.equipped[held]=true
            local big=put(p.inventory,makeItem("Base.Log",{weight=10}))
            local function e(item) return {x=12,y=12,z=0,o=1,c=0,t="shelves",id=item.id} end
            sent={}; synced={}
            -- The indexes point at the other crate, so the type picks the shelf.
            S.command(p,"return",{request="b1",items={e(saw),e(fav),e(held),e(big),e(makeItem("Base.Gone"))}})
            assert(saw.container==shelf and fav.container==p.inventory and held.container==p.inventory and big.container==p.inventory)
            assert(sent[1].args.returned==1 and sent[1].args.kept==3 and #synced==2)
            -- Two containers of the same type: the index picks the one the item came from.
            local twin=crate(spot,{name="twin",type="shelves"})
            S.command(p,"return",{request="b3",items={{x=12,y=12,z=0,o=2,c=0,t="shelves",id=hammer.id}}})
            assert(hammer.container==twin)
            p.inventory:Remove(hammer); p.inventory:AddItem(hammer)
            -- Too far now: kept in the inventory, never dropped.
            p.x=40; p.y=40
            sent={}; S.command(p,"return",{request="b2",items={e(hammer)}})
            assert(hammer.container==p.inventory and sent[1].args.kept==1)
        ''')

    def test_craft_fetches_before_start_and_sends_leftovers_back(self):
        self.check('''
            isClient=function() return true end
            local F=require "BSCCraft/Finder"
            local H=require "BSCCraft/Hooks"
            local C=require "BSCCraft/Craft"
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=0}
            clientArea({x1=0,y1=0,x2=19,y2=19})
            local p=makePlayer(1,1,0); players[0]=p; makeSquare(1,1,0)
            local remote=crate(makeSquare(15,15,0),{name="remote"})
            local plank=put(remote,makeItem("Base.Plank"))
            local plank2=put(remote,makeItem("Base.Plank"))
            local saw=put(remote,makeItem("Base.Saw"))
            vanillaUI({})
            ISHandcraftAction=makeHandcraftClass()
            H.install(); C.install()
            F.extra(p); scanAll(F)
            local recipe={needs={{type="Base.Plank",count=1},{type="Base.Saw",count=1}},getName=function() return "TestRecipe" end}
            local function newAction(manual) return ISHandcraftAction:new(p,recipe,H.extended(p),manual or false,nil) end
            local function consume(item) return function(self) p.inventory:Remove(item) end end
            local a1,a2=newAction(),newAction()
            queues[p]={queue={a1,a2}}
            assert(a1:waitToStart()==true)
            local request=lastClient("fetch").args
            assert(ids(request.items)==plank.id..","..saw.id)
            assert(request.items[1].x==15 and request.items[1].y==15 and request.items[1].o==0 and request.items[1].c==0 and request.items[1].t=="crate")
            assert(a1:waitToStart()==true and #clientSent==1)
            -- The reply alone isn't enough: the items must have arrived in the inventory.
            C.receive("fetch",{request=request.request,ok=true})
            assert(a1:waitToStart()==true)
            serverMoves(p,{plank,saw})
            assert(a1:waitToStart()==false)
            a1:start()
            assert(a1.started and a1.startedWith:size()==1 and a1.startedWith:get(0)==p.inventory)
            -- A following handcraft inherits the saw instead of sending it back and forth.
            a1.consume=consume(plank); a1:perform()
            assert(a1.performed and not lastClient("return") and #a2.bsccCarry==2)
            table.remove(queues[p].queue,1)
            assert(a2:waitToStart()==true)
            request=lastClient("fetch").args
            assert(ids(request.items)==tostring(plank2.id))
            serverMoves(p,{plank2}); C.receive("fetch",{request=request.request,ok=true})
            assert(a2:waitToStart()==false)
            a2:start(); a2.consume=consume(plank2); a2:perform()
            local back=lastClient("return").args
            assert(ids(back.items)==tostring(saw.id) and back.items[1].x==15 and back.items[1].t=="crate")
            -- Refused fetch: the craft stops before vanilla start and says why.
            p.inventory:Remove(saw); remote:AddItem(saw); remote:AddItem(plank2)
            clientSent={}
            local a3=newAction(); queues[p]={queue={a3}}
            assert(a3:waitToStart()==true)
            C.receive("fetch",{request=lastClient("fetch").args.request,ok=false,code="missing"})
            assert(a3:waitToStart()==false)
            a3:start()
            assert(a3.forced and not a3.started and p.halo=="IGUI_BSCCraft_Fetch_missing")
            -- No answer in time.
            local a4=newAction(); queues[p]={queue={a4}}
            assert(a4:waitToStart()==true)
            time=time+C.timeout
            assert(a4:waitToStart()==false)
            a4:start(); assert(a4.forced and p.halo=="IGUI_BSCCraft_Fetch_timeout")
            -- A success that shows up after the timeout is sent straight back.
            clientSent={}
            serverMoves(p,{plank2,saw}); C.receive("fetch",{request=a4.bscc.request,ok=true})
            assert(ids(lastClient("return").args.items)==plank2.id..","..saw.id)
            p.inventory:Remove(plank2); p.inventory:Remove(saw); remote:AddItem(plank2); remote:AddItem(saw)
            -- Cancelled while waiting: whatever arrives later goes straight back.
            clientSent={}
            local a5=newAction(); queues[p]={queue={a5}}
            assert(a5:waitToStart()==true)
            local pending=lastClient("fetch").args
            a5:interruptWaitToStart()
            assert(a5.interrupted)
            serverMoves(p,{plank2,saw}); C.receive("fetch",{request=pending.request,ok=true})
            assert(ids(lastClient("return").args.items)==plank2.id..","..saw.id)
            -- Manual picks are fetched as chosen.
            p.inventory:Remove(plank2); p.inventory:Remove(saw); remote:AddItem(plank2); remote:AddItem(saw)
            clientSent={}
            local a6=newAction({[1]=list({plank2})}); queues[p]={queue={a6}}
            assert(a6:waitToStart()==true and ids(lastClient("fetch").args.items)==tostring(plank2.id))
            -- Nothing remote needed: no request, and remote containers still leave the action.
            local hand=put(p.inventory,makeItem("Base.Saw")); put(p.inventory,makeItem("Base.Plank"))
            clientSent={}
            local a7=newAction(); queues[p]={queue={a7}}
            assert(a7:waitToStart()==false and #clientSent==0)
            a7:start(); assert(a7.startedWith:size()==1)
            local vanilla=ISInventoryPaneContextMenu.getContainers(p)
            local a8=ISHandcraftAction:new(p,recipe,vanilla,false,nil)
            assert(a8:waitToStart()==false); a8:start(); assert(a8.startedWith==vanilla)
            -- Adding to an empty queue starts the action at once, still inside the craft button's scope.
            p.inventory:Remove(hand)
            clientSent={}
            local a9=newAction(); queues[p]={queue={a9}}
            local waited=H.scoped(function() local w=a9:waitToStart(); a9:start(); return w end)()
            assert(waited==true and ids(lastClient("fetch").args.items)==tostring(saw.id))
            local a10=newAction(); queues[p]={queue={a10}}
            a10.bscc={state="ready"}
            H.scoped(function() a10:start() end)()
            assert(a10.startedWith:size()==1)
            p.inventory:AddItem(hand)
            -- Disorganized characters keep what they fetched, like vanilla.
            p.traits[CharacterTrait.DISORGANIZED]=true
            a8.bsccCarry={{x=15,y=15,z=0,o=0,c=0,t="crate",id=hand.id}}
            clientSent={}; queues[p]={queue={a8}}; a8:perform()
            assert(#clientSent==0)
        ''')

    def test_single_player_round_trip_uses_the_real_service(self):
        self.check('''
            local F=require "BSCCraft/Finder"
            local H=require "BSCCraft/Hooks"
            local C=require "BSCCraft/Craft"
            local S=require "BSCCraft/Service"
            BSCCraftFromContainers={server=S,client=C}
            SandboxVars.BSCCraft={BaseArea=true,NearbyRadius=0}
            serverArea({x1=0,y1=0,x2=19,y2=19})
            local p=makePlayer(1,1,0); players[0]=p; makeSquare(1,1,0)
            local remote=crate(makeSquare(15,15,1),{name="remote"})
            local plank=put(remote,makeItem("Base.Plank"))
            local saw=put(remote,makeItem("Base.Saw"))
            vanillaUI({})
            ISHandcraftAction=makeHandcraftClass()
            H.install(); C.install()
            F.extra(p); scanAll(F)
            local recipe={needs={{type="Base.Plank",count=1},{type="Base.Saw",count=1}},getName=function() return "TestRecipe" end}
            local a=ISHandcraftAction:new(p,recipe,H.extended(p),false,nil)
            queues[p]={queue={a}}
            -- Single-player answers synchronously, so the action never waits.
            assert(a:waitToStart()==false)
            assert(plank.container==p.inventory and saw.container==p.inventory and #synced==0 and #sent==0)
            a:start(); assert(a.startedWith:size()==1)
            a.consume=function() p.inventory:Remove(plank) end
            a:perform()
            assert(saw.container==remote and plank.container==nil and #remote.items==1)
        ''')


if __name__ == "__main__":
    unittest.main(verbosity=2)
