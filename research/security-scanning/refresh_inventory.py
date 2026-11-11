"""Print a dated metadata comparison for the public GitHub repositories in the register."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def github(path):
    request = Request('https://api.github.com/repos/' + path, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'commonwealth-public-source-inventory'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def observe(repo, fetch=github):
    slug = re.fullmatch(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', repo['repository'])
    if not slug or any(part in ('.', '..') for part in slug[1].split('/')):
        raise ValueError('invalid public GitHub repository URL')
    path = slug[1]
    header = fetch(path)
    commits = fetch(path + '/commits?per_page=1')
    try:
        release = fetch(path + '/releases/latest')
    except HTTPError as exc:
        if exc.code != 404:
            raise
        release = None
    head = commits[0] if commits else None
    return dict(citation_id=repo['citation_id'], repository=repo['repository'],
                previous_revision=repo['head_revision'], revision=head['sha'] if head else None,
                committed_at=head['commit']['committer']['date'] if head else None,
                default_branch=header['default_branch'], archived=header['archived'],
                primary_language=header.get('language'), github_license_id=(header.get('license') or {}).get('spdx_id'),
                release=({k: release[k] for k in ('tag_name', 'published_at', 'html_url')} if release else None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('citation_ids', nargs='*', help='leave empty to check all inventoried repositories')
    args = parser.parse_args()
    baseline = json.loads(Path(__file__).with_name('source-inventory.json').read_text(encoding='utf-8'))
    repos = {r['citation_id']: r for r in baseline['repositories']}
    selection = list(dict.fromkeys(args.citation_ids)) or list(repos)
    if unknown := set(selection) - repos.keys():
        parser.error('unknown repository citation: ' + ', '.join(sorted(unknown)))
    observed, errors = [], []
    for key in selection:
        try:
            observed.append(observe(repos[key]))
        except (OSError, URLError, ValueError, KeyError, IndexError) as exc:
            errors.append(dict(citation_id=key, error=str(exc)))
    print(json.dumps(dict(schema='public-repository-metadata-refresh-1',
                          inspected_at=datetime.now(timezone.utc).isoformat(), observations=observed,
                          errors=errors), indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
