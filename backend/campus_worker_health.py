import os
import time
import redis
from campus_runtime import assert_runtime_identity

assert_runtime_identity()
client = redis.Redis.from_url(os.environ['REDIS_URL'], socket_timeout=2)
heartbeat = client.get('campus_perf:' + os.environ['CAMPUS_RUN_ID'] + ':worker:heartbeat')
raise SystemExit(0 if heartbeat and time.time() - float(heartbeat) < 20 else 1)
