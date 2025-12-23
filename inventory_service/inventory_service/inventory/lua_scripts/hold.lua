local available_key = "event:" .. ARGV[1] .. ":available"
local held_key = "event:" .. ARGV[1] .. ":held"
local hold_key = "hold:" .. ARGV[3]

local available = tonumber(redis.call('GET', available_key) or '0')
local quantity = tonumber(ARGV[2])
local ttl = tonumber(ARGV[4])

if available >= quantity and quantity > 0 then
    redis.call('DECRBY', available_key, quantity)
    redis.call('INCRBY', held_key, quantity)
    redis.call('SET', hold_key, quantity, 'EX', ttl)
    return 1
else
    return 0
end