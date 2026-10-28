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


if __name__ == "__main__":
    unittest.main(verbosity=2)
