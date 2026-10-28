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


if __name__ == "__main__":
    unittest.main(verbosity=2)
