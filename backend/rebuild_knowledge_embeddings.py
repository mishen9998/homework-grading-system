"""Backfill or rebuild approved knowledge vectors without calling DeepSeek."""
import argparse

from run import app
from app.services.knowledge_search import active_encoder_name, rebuild_embeddings
from app.services.runtime_control import bump_knowledge_version


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', choices=['student', 'teacher'])
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    with app.app_context():
        count = rebuild_embeddings(library=args.library, force=args.force)
        for library in ([args.library] if args.library else ['student', 'teacher']):
            bump_knowledge_version(library)
        print(f'Indexed {count} approved entries with {active_encoder_name()}')
