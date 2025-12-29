import os
import redis
from django.conf import settings

# Prefer REDIS_URL if provided (Render/managed Redis). Fallback to host/port.
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
	r = redis.from_url(REDIS_URL)
else:
	REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
	REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
	r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Load Lua scripts from an absolute path to avoid CWD issues
BASE_DIR = getattr(settings, 'BASE_DIR', os.getcwd())
LUA_DIR = os.path.join(BASE_DIR, 'inventory', 'lua_scripts')
HOLD_SCRIPT = open(os.path.join(LUA_DIR, 'hold.lua')).read()
RELEASE_SCRIPT = open(os.path.join(LUA_DIR, 'release.lua')).read()
SELL_SCRIPT = open(os.path.join(LUA_DIR, 'sell.lua')).read()

hold_sha = r.script_load(HOLD_SCRIPT)
release_sha = r.script_load(RELEASE_SCRIPT)
sell_sha = r.script_load(SELL_SCRIPT)