"""Execute a maintenance command with credentials inherited from our live PID 1."""
import os
import sys
from pathlib import Path

if __name__ == '__main__':
    # Only called after the host controller verifies this run's Docker ownership.
    values = Path('/proc/1/environ').read_bytes().split(b'\0')
    parent = dict(item.decode().split('=', 1) for item in values if b'=' in item)
    for name, value in parent.items():
        if name in {'DATABASE_URL', 'REDIS_URL', 'QDRANT_URL', 'QDRANT_COLLECTION',
                    'QDRANT_CHUNK_COLLECTION', 'CAMPUS_RUN_ID', 'CAMPUS_FIXTURE_PASSWORD',
                    'SECRET_KEY', 'JWT_SECRET_KEY', 'UPLOAD_FOLDER'}:
            os.environ[name] = value
    from campus_runtime import assert_runtime_identity
    assert_runtime_identity()
    os.execvp(sys.argv[1], sys.argv[1:])
