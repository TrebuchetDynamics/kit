#!/usr/bin/env python3
"""Shortlist Forever components offline and retrieve one pinned tile at a time."""

import argparse
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import re
import sys
from urllib import request

SKILL = Path(__file__).resolve().parents[1]


class PinnedSourceOnly(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def pinned_bytes(pin, name):
    data = (SKILL / 'upstream' / name).read_bytes()
    if sha256(data).hexdigest() != pin['files'][name]:
        raise ValueError(f'Checksum mismatch for {name}; restore the packaged Forever skill.')
    return data


def search(pin, components, text, filters, parser):
    facets = json.loads(pinned_bytes(pin, 'facets.json'))['facets']
    terms = text.casefold().split()
    if not (terms or filters):
        parser.error('give --text or at least one --facet to shortlist components')
    required = []
    for pair in filters:
        key, _, value = pair.partition('=')
        if key == 'a11y' or value not in facets.get(key, {}):
            parser.error(f'unsupported facet {pair!r}; see upstream/facets.json (except a11y)')
        required.append((key, value))

    matches = []
    for tile in components:
        keywords = ' '.join([tile['title'], tile['description'], *tile.get('tags', [])]).casefold()
        if not all(term in keywords for term in terms):
            continue
        for key, expected in required:
            value = tile['palette']['scheme'] if key == 'scheme' else tile.get(key)
            if not (expected in value if isinstance(value, list) else value == expected):
                break
        else:
            # The index may have stale descriptions; read the selected source before adapting.
            matches.append({key: tile[key] for key in (
                'file', 'title', 'description', 'role', 'technique', 'motion', 'perfTier', 'deps')})
            if len(matches) == 3:
                break
    print(json.dumps(matches, ensure_ascii=False, indent=2))


def fetch(pin, tile, destination):
    source_path = tile['repoFile']
    owner_repo = pin['repository'].removeprefix('https://github.com/')
    url = f"https://raw.githubusercontent.com/{owner_repo}/{pin['revision']}/{source_path}"
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        raise ValueError('Choose a new output directory under an existing parent.')
    notices = {name: pinned_bytes(pin, name) for name in ('LICENSE', 'NOTICE.md')}
    try:
        with request.build_opener(PinnedSourceOnly()).open(url, timeout=15) as response:
            if response.status != 200:
                raise ValueError(f'expected a complete component response, got HTTP {response.status}')
            # At this pin all indexed HTML files are under 16 KiB.
            limit = 64 * 1024
            data = response.read(limit + 1)
            if not data or len(data) > limit:
                raise ValueError('empty or oversized component response')
            # A bounded read can return short data rather than raising on early EOF.
            length = response.headers.get('Content-Length')
            if length is not None and len(data) != int(length):
                raise ValueError('incomplete component response')
    except (OSError, ValueError, HTTPException) as exc:
        raise ValueError(f'Fetch failed for {url}: {exc}. Restore access to the pinned URL and retry.') from exc

    receipt = {
        'title': tile['title'], 'repository': pin['repository'], 'revision': pin['revision'],
        'source_path': source_path, 'source_url': url, 'sha256': sha256(data).hexdigest(),
        'license': pin['license'], 'file': Path(tile['file']).name,
    }
    destination.mkdir()
    (destination / receipt['file']).write_bytes(data)
    for name, contents in notices.items():
        (destination / name).write_bytes(contents)
    (destination / 'provenance.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(destination / 'provenance.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    shortlist = commands.add_parser('search', help='Print at most three matches without network access')
    shortlist.add_argument('--text', default='', help='Words to match in title, description or tags')
    shortlist.add_argument('--facet', action='append', default=[], metavar='FIELD=VALUE',
                           help='Require an exact facet value (repeat to require all filters)')
    retrieve = commands.add_parser('fetch', help='Save one indexed tile, its provenance and notices')
    retrieve.add_argument('file', help='Exact file path from the shortlist')
    retrieve.add_argument('destination', type=Path, help='New directory under an existing parent')
    args = parser.parse_args(argv)
    try:
        pin = json.loads((SKILL / 'UPSTREAM.json').read_bytes())
        components = json.loads(pinned_bytes(pin, 'components.index.json'))['components']
        if args.command == 'search':
            search(pin, components, args.text, args.facet, shortlist)
        else:
            tile = next((tile for tile in components if tile['file'] == args.file), None)
            if (not tile or not re.fullmatch(r'[a-z0-9-]+/[a-z0-9-]+\.html', args.file)
                    or tile['repoFile'] != f'infinite/{args.file}'):
                retrieve.error('not a catalog tile; choose an exact file from search')
            fetch(pin, tile, args.destination)
    except (OSError, ValueError) as exc:
        print(f'Forever catalog: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
