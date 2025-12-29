local held_key = "event:" .. ARGV[1] .. ":held"
local available_key = "event:" .. ARGV[1] .. ":available"
local hold_key = "hold:" .. ARGV[3]

local held_quantity = tonumber(redis.call('GET', hold_key) or '0')
local quantity = tonumber(ARGV[2])

if held_quantity >= quantity and quantity > 0 then
    redis.call('DECRBY', held_key, quantity)
    redis.call('INCRBY', available_key, quantity)
    redis.call('DEL', hold_key)
    return 1
else
    return 0
end