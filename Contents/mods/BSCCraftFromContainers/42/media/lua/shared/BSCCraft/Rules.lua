-- Pure Lua 5.1: placement rules and request validation shared by the client and the server.
local R = { reach=3, slack=2, maxSide=256, maxRadius=15, maxEntries=200 }

local function between(n, lo, hi)
    return type(n) == "number" and n == n and n % 1 == 0 and n >= lo and n <= hi
end

local function integer(n)
    return between(n, 0, 1000000)
end

-- Accepts Base Stock Counter's inclusive bounds. The side limit only bounds scan cost.
function R.area(a)
    if type(a) ~= "table" then return nil end
    for _, k in ipairs({"x1", "y1", "x2", "y2"}) do
        if not integer(a[k]) then return nil end
    end
    if a.x2 < a.x1 or a.y2 < a.y1 or a.x2-a.x1+1 > R.maxSide or a.y2-a.y1+1 > R.maxSide then return nil end
    return {x1=a.x1, y1=a.y1, x2=a.x2, y2=a.y2}
end

function R.key(a)
    return a and (a.x1..":"..a.y1..":"..a.x2..":"..a.y2) or nil
end

function R.inside(a, x, y, margin)
    margin = margin or 0
    return a ~= nil and x >= a.x1-margin and x <= a.x2+margin and y >= a.y1-margin and y <= a.y2+margin
end

function R.distance(ax, ay, bx, by)
    return math.max(math.abs(ax-bx), math.abs(ay-by))
end

-- Sandbox values arrive from the server; clamp them instead of trusting them.
function R.options(raw)
    if type(raw) ~= "table" then raw = {} end
    local radius = tonumber(raw.NearbyRadius) or 5
    local limit = tonumber(raw.MaxBaseContainers) or 256
    return {
        base = raw.BaseArea ~= false,
        radius = math.max(0, math.min(R.maxRadius, math.floor(radius))),
        limit = math.max(16, math.min(1024, math.floor(limit))),
    }
end

-- What the client offers to crafting: the whole base while standing in it, or the same floor nearby.
-- The same-building check for nearby containers needs world objects, so the finder applies it.
function R.clientKind(o, px, py, pz, tx, ty, tz, area)
    if o.base and area and R.inside(area, px, py) and R.inside(area, tx, ty) then return "base" end
    if o.radius > 0 and tz == pz and R.distance(px, py, tx, ty) <= o.radius then return "nearby" end
    return nil
end

-- What the server moves items from or back to. Slack covers player movement between the client's
-- choice and the request reaching the server.
function R.serverKind(o, px, py, pz, tx, ty, tz, area)
    local d, dz = R.distance(px, py, tx, ty), math.abs(tz-pz)
    if d <= R.reach+R.slack and dz <= 1 then return "reach" end
    if o.radius > 0 and d <= o.radius+R.slack and dz <= 1 then return "nearby" end
    if o.base and area and R.inside(area, px, py, R.slack) and R.inside(area, tx, ty) then return "base" end
    return nil
end

-- Closest first, so the limit drops the farthest containers and recipes prefer nearby stock.
function R.nearest(entries, px, py, pz, limit)
    for _, e in ipairs(entries) do
        e.d = R.distance(px, py, e.x, e.y) + math.abs(e.z-pz)
    end
    table.sort(entries, function(a, b)
        if a.d ~= b.d then return a.d < b.d end
        if a.z ~= b.z then return a.z < b.z end
        if a.y ~= b.y then return a.y < b.y end
        if a.x ~= b.x then return a.x < b.x end
        return a.i < b.i
    end)
    local out = {}
    for i=1,math.min(#entries, limit) do out[i] = entries[i] end
    return out
end

function R.same(a, b)
    if #a ~= #b then return false end
    for i=1,#a do
        if a[i].container ~= b[i].container then return false end
    end
    return true
end

function R.token(s)
    return type(s) == "string" and #s > 0 and #s <= 64
end

-- Items named by a client: where the container is, which one it is and the item ID. Anything
-- malformed rejects the whole request; the server still checks every entry against the world.
function R.entries(list)
    if type(list) ~= "table" then return nil end
    local out, seen = {}, {}
    for i=1,R.maxEntries+1 do
        local e = list[i]
        if e == nil then break end
        if i > R.maxEntries or type(e) ~= "table" then return nil end
        if not (integer(e.x) and integer(e.y) and between(e.z, -64, 64) and between(e.o, 0, 100000)
            and between(e.c, 0, 1000) and between(e.id, -2147483648, 2147483647)) then return nil end
        -- The container type is only compared for equality on the server.
        if type(e.t) ~= "string" or #e.t == 0 or #e.t > 64 or e.t:find("%c") or seen[e.id] then return nil end
        seen[e.id] = true
        out[i] = {x=e.x, y=e.y, z=e.z, o=e.o, c=e.c, t=e.t, id=e.id}
    end
    if #out == 0 then return nil end
    return out
end

-- Chunk-aligned rectangles that cover the area exactly once.
function R.tiles(a, size)
    local out = {}
    for cy=math.floor(a.y1/size),math.floor(a.y2/size) do
        for cx=math.floor(a.x1/size),math.floor(a.x2/size) do
            out[#out+1] = {cx=cx, cy=cy,
                x1=math.max(a.x1, cx*size), y1=math.max(a.y1, cy*size),
                x2=math.min(a.x2, cx*size+size-1), y2=math.min(a.y2, cy*size+size-1)}
        end
    end
    return out
end

return R
