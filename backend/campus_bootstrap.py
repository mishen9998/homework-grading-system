"""Read fresh run credentials from stdin, never Docker arguments or a secret file."""
import json
import os
import sys


def main():
    config = json.loads(sys.stdin.readline())
    if not isinstance(config, dict) or not all(isinstance(v, str) for v in config.values()):
        raise SystemExit('invalid runtime envelope')
    os.environ.update(config)
    # This process becomes the long-lived app/worker. Docker Config.Env has no keys.
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
