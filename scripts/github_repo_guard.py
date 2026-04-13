#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / 'repo-guard.config.json'
PERMISSION_RANK = {
    'NONE': 0,
    'READ': 1,
    'TRIAGE': 2,
    'WRITE': 3,
    'MAINTAIN': 4,
    'ADMIN': 5,
}

def fail(message, detail=None):
    print(f"\n[repo-guard] {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    sys.exit(1)

def run(*args):
    try:
        return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.STDOUT, text=True).strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError((e.output or '').strip() or str(e))

if not CONFIG_PATH.exists():
    fail('Missing repo-guard.config.json. This project must declare its expected GitHub target.')

config = json.loads(CONFIG_PATH.read_text())
expected_repo = config.get('expectedRepo')
required_permission = str(config.get('requiredPermission', 'WRITE')).upper()
allowed_permissions = [str(x).upper() for x in config.get('allowedPermissions', ['WRITE', 'MAINTAIN', 'ADMIN'])]

if not expected_repo:
    fail('repo-guard.config.json is missing expectedRepo.')

try:
    remote_url = run('git', 'remote', 'get-url', 'origin')
except RuntimeError as e:
    fail('Could not read git origin remote.', str(e))

m = re.search(r'github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$', remote_url, re.I)
if not m:
    fail('Origin remote is not a recognizable GitHub repo URL.', f'origin = {remote_url}')

actual_repo = m.group(1)
if actual_repo != expected_repo:
    fail('Origin remote does not match this project\'s declared company repo.', f'expected = {expected_repo}\nactual   = {actual_repo}')

try:
    run('gh', 'auth', 'status')
except RuntimeError:
    fail('GitHub CLI is not authenticated. Refusing push-related operations for this company project.', 'Run: gh auth login (with the company account that has write access)')

try:
    gh_user = run('gh', 'api', 'user', '--jq', '.login')
    repo_meta = json.loads(run('gh', 'repo', 'view', expected_repo, '--json', 'nameWithOwner,viewerPermission'))
except RuntimeError as e:
    fail('Could not read current GitHub account/repo permission info via gh.', str(e))

viewer_permission = str(repo_meta.get('viewerPermission', 'NONE')).upper()
actual_rank = PERMISSION_RANK.get(viewer_permission, -1)
required_rank = PERMISSION_RANK.get(required_permission, PERMISSION_RANK['WRITE'])

if viewer_permission not in allowed_permissions or actual_rank < required_rank:
    fail('Current GitHub account does not have enough permission for this company repo.', f'repo      = {expected_repo}\naccount   = {gh_user}\npermission= {viewer_permission}\nrequired  = {required_permission}+')

print('\n[repo-guard] OK')
print(f'repo       : {expected_repo}')
print(f'origin     : {remote_url}')
print(f'gh account : {gh_user}')
print(f'permission : {viewer_permission}')
