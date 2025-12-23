local event_key = "event:" .. ARGV[1] .. ":available"
local held_key = "event:" .. ARGV[1] .. ":held"
local hold_key = "hold:" .. ARGV[3]

local available = tonumber(redis.call('GET', event_key) or '0')
local quantity = tonumber(ARGV[2])
local ttl = tonumber(ARGV[4])

if available >= quantity then
    redis.call('DECRBY', event_key, quantity)
    redis.call('INCRBY', held_key, quantity)
    redis.call('SET', hold_key, quantity, 'EX', ttl)
    return 1
else
    return 0
end