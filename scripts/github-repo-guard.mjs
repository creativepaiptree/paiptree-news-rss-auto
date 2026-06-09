#!/usr/bin/env node
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(ROOT, 'repo-guard.config.json');

const PERMISSION_RANK = {
  NONE: 0,
  READ: 1,
  TRIAGE: 2,
  WRITE: 3,
  MAINTAIN: 4,
  ADMIN: 5,
};

const fail = (message, detail) => {
  console.error(`\n[repo-guard] ${message}`);
  if (detail) console.error(detail);
  process.exit(1);
};

const run = (command, args, options = {}) => {
  try {
    return execFileSync(command, args, {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
      ...options,
    }).trim();
  } catch (error) {
    const stderr = error?.stderr?.toString?.().trim();
    const stdout = error?.stdout?.toString?.().trim();
    throw new Error(stderr || stdout || error.message);
  }
};

if (!existsSync(CONFIG_PATH)) {
  fail('Missing repo-guard.config.json. This project must declare its expected GitHub target.');
}

const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
const expectedRepo = config.expectedRepo;
const expectedGithubUser = config.expectedGithubUser;
const autoSwitchGithubUser = config.autoSwitchGithubUser !== false;
const allowedPermissions = config.allowedPermissions ?? ['WRITE', 'MAINTAIN', 'ADMIN'];
const requiredPermission = config.requiredPermission ?? 'WRITE';

if (!expectedRepo) fail('repo-guard.config.json is missing expectedRepo.');

let remoteUrl;
try {
  remoteUrl = run('git', ['remote', 'get-url', 'origin']);
} catch (error) {
  fail('Could not read git origin remote.', error.message);
}

const match = remoteUrl.match(/github\.com[^:/]*[:/]([^/]+\/[^/.]+)(?:\.git)?$/i);
if (!match) fail('Origin remote is not a recognizable GitHub repo URL.', `origin = ${remoteUrl}`);

const actualRepo = match[1];
if (actualRepo !== expectedRepo) {
  fail('Origin remote does not match this project\'s declared GitHub repo.', `expected = ${expectedRepo}\nactual   = ${actualRepo}`);
}

try {
  run('gh', ['auth', 'status']);
} catch {
  fail('GitHub CLI is not authenticated. Refusing push-related operations for this project.', 'Run: gh auth login with an account that has write access');
}

let ghUser;
try {
  ghUser = run('gh', ['api', 'user', '--jq', '.login']);
} catch (error) {
  fail('Could not determine current GitHub login.', error.message);
}

let switchedGithubUser = null;
if (expectedGithubUser && ghUser !== expectedGithubUser) {
  if (!autoSwitchGithubUser) {
    fail(
      'Current GitHub account does not match this project\'s declared GitHub user.',
      `expected = ${expectedGithubUser}\nactual   = ${ghUser}`,
    );
  }

  try {
    run('gh', ['auth', 'switch', '--hostname', 'github.com', '--user', expectedGithubUser]);
    switchedGithubUser = `${ghUser} -> ${expectedGithubUser}`;
    ghUser = run('gh', ['api', 'user', '--jq', '.login']);
  } catch (error) {
    fail(
      'Could not auto-switch GitHub account for this project.',
      `expected = ${expectedGithubUser}\nactual   = ${ghUser}\nreason   = ${error.message}`,
    );
  }

  if (ghUser !== expectedGithubUser) {
    fail(
      'GitHub account auto-switch did not select the expected account.',
      `expected = ${expectedGithubUser}\nactual   = ${ghUser}`,
    );
  }
}

let repoMeta;
try {
  repoMeta = JSON.parse(run('gh', ['repo', 'view', expectedRepo, '--json', 'nameWithOwner,viewerPermission']));
} catch (error) {
  fail('Could not read repo permission info via gh.', error.message);
}

const viewerPermission = String(repoMeta.viewerPermission || 'NONE').toUpperCase();
const actualRank = PERMISSION_RANK[viewerPermission] ?? -1;
const requiredRank = PERMISSION_RANK[requiredPermission] ?? PERMISSION_RANK.WRITE;
const allowList = allowedPermissions.map((item) => String(item).toUpperCase());
const allowSet = new Set(allowList);

if (!allowSet.has(viewerPermission) || actualRank < requiredRank) {
  fail('Current GitHub account does not have enough permission for this repo.', `repo      = ${expectedRepo}\naccount   = ${ghUser}\npermission= ${viewerPermission}\nrequired  = ${requiredPermission}+`);
}

console.log('\n[repo-guard] OK');
console.log(`repo       : ${expectedRepo}`);
console.log(`origin     : ${remoteUrl}`);
console.log(`gh account : ${ghUser}`);
if (switchedGithubUser) console.log(`auto-switch: ${switchedGithubUser}`);
console.log(`permission : ${viewerPermission}`);
