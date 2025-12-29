import os
import redis
from django.conf import settings

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Load scripts
HOLD_SCRIPT = open('inventory/lua_scripts/hold.lua').read()
RELEASE_SCRIPT = open('inventory/lua_scripts/release.lua').read()
SELL_SCRIPT = open('inventory/lua_scripts/sell.lua').read()

hold_sha = r.script_load(HOLD_SCRIPT)
release_sha = r.script_load(RELEASE_SCRIPT)
sell_sha = r.script_load(SELL_SCRIPT)