local G={last={}}
function G.log(key, err)
    local now=getTimestampMs()
    if not G.last[key] or now-G.last[key]>=30000 then
        G.last[key]=now
        print("[BSCCraftFromContainers] "..key..": "..tostring(err))
    end
end
function G.call(key, fn, onError)
    return function(...)
        local ok,err=pcall(fn,...)
        if ok then return err end
        G.log(key,err)
        if onError then
            local recovered, recoveryError=pcall(onError,err)
            if not recovered then G.log(key.." recovery",recoveryError) end
        end
    end
end
return G
