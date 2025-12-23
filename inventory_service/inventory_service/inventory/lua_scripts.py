import redis
from django.conf import settings

r = redis.Redis(host='localhost', port=6379, db=0)

# Load scripts
HOLD_SCRIPT = open('inventory/lua_scripts/hold.lua').read()
RELEASE_SCRIPT = open('inventory/lua_scripts/release.lua').read()
SELL_SCRIPT = open('inventory/lua_scripts/sell.lua').read()

hold_sha = r.script_load(HOLD_SCRIPT)
release_sha = r.script_load(RELEASE_SCRIPT)
sell_sha = r.script_load(SELL_SCRIPT)