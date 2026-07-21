#!/usr/bin/env node

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const DEFAULTS = {
  api: 'http://127.0.0.1:5000',
  db: 'discogs_data_all.json',
  rpm: 500,
  tpm: 500000,
  concurrency: 32,
  maxRetries: 6,
  aiVersion: 2,
  responseTokenReserve: 1200,
};

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function parseArgs(argv) {
  const options = { ...DEFAULTS, force: false, dryRun: false, limit: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => argv[++index];
    switch (arg) {
      case '--api': options.api = next(); break;
      case '--db': options.db = next(); break;
      case '--rpm': options.rpm = Number(next()); break;
      case '--tpm': options.tpm = Number(next()); break;
      case '--concurrency': options.concurrency = Number(next()); break;
      case '--max-retries': options.maxRetries = Number(next()); break;
      case '--ai-version': options.aiVersion = Number(next()); break;
      case '--response-token-reserve': options.responseTokenReserve = Number(next()); break;
      case '--limit': options.limit = Number(next()); break;
      case '--force': options.force = true; break;
      case '--dry-run': options.dryRun = true; break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }
  validateOptions(options);
  options.api = options.api.replace(/\/$/, '');
  return options;
}

function validateOptions(options) {
  for (const key of ['rpm', 'tpm', 'concurrency', 'maxRetries', 'aiVersion', 'responseTokenReserve']) {
    if (!Number.isFinite(options[key]) || options[key] < 0) {
      const flagName = key.replace(/[A-Z]/g, match => '-' + match.toLowerCase());
      throw new Error(`--${flagName} must be a positive number`);
    }
  }
  if (options.rpm < 1 || options.tpm < 1 || options.concurrency < 1) {
    throw new Error('--rpm, --tpm, and --concurrency must be at least 1');
  }
  if (options.limit !== null && (!Number.isFinite(options.limit) || options.limit < 1)) {
    throw new Error('--limit must be at least 1');
  }
}

function printHelp() {
  console.log(`AI enrich uncached Discogs releases via the running Flask backend.

Usage:
  npx ai-enrich-collection [options]
  npm run ai:enrich -- [options]

Options:
  --api <url>                    Flask API base URL (default: ${DEFAULTS.api})
  --db <path>                    pysondb JSON database (default: ${DEFAULTS.db})
  --rpm <number>                 requests per minute limit (default: ${DEFAULTS.rpm})
  --tpm <number>                 estimated tokens per minute limit (default: ${DEFAULTS.tpm})
  --concurrency <number>         concurrent in-flight enrich requests (default: ${DEFAULTS.concurrency})
  --max-retries <number>         retries per release for 429/5xx/network failures (default: ${DEFAULTS.maxRetries})
  --response-token-reserve <n>   estimated response tokens per release (default: ${DEFAULTS.responseTokenReserve})
  --ai-version <number>          cache version considered valid (default: ${DEFAULTS.aiVersion})
  --limit <number>               process only first N uncached releases
  --force                        enrich even when release.ai.version is cached
  --dry-run                      print plan without calling Azure/backend
`);
}

async function loadReleases(dbPath) {
  const absolutePath = path.resolve(process.cwd(), dbPath);
  const raw = await readFile(absolutePath, 'utf8');
  const parsed = JSON.parse(raw);
  const releases = Array.isArray(parsed) ? parsed : parsed.data;
  if (!Array.isArray(releases)) {
    throw new TypeError(`${dbPath} must contain a JSON array or a pysondb { data: [] } payload`);
  }
  return { releases, absolutePath };
}

async function verifyApiAvailable(options, pending) {
  const firstRelease = pending.find(release => releaseId(release) != null);
  const releasePath = firstRelease ? `/api/releases/${encodeURIComponent(releaseId(firstRelease))}` : '/api/chat/context';
  const url = `${options.api}${releasePath}`;
  let response;
  try {
    response = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(5000) });
  } catch (error) {
    throw new Error(`Flask API is not reachable at ${options.api}. Start the backend first, then rerun the enrich command. Details: ${error.message}`);
  }
  if (!response.ok) {
    const body = await safeJson(response);
    throw new Error(`Flask API preflight failed at ${url}: HTTP ${response.status} ${body.error || response.statusText}`);
  }
}

function isCached(release, aiVersion) {
  return release?.ai && Number(release.ai.version) === aiVersion;
}

function releaseId(release) {
  return release?.release_id ?? release?.id;
}

function releaseIdKey(release) {
  const id = releaseId(release);
  return id == null ? null : String(id);
}

function releaseIdSnapshot(releases) {
  const ids = releases.map(releaseIdKey).filter(Boolean).sort();
  return {
    count: releases.length,
    ids,
    uniqueCount: new Set(ids).size,
  };
}

function assertReleaseIntegrity(before, after) {
  const missing = before.ids.filter(id => !after.ids.includes(id));
  const added = after.ids.filter(id => !before.ids.includes(id));
  const countChanged = before.count !== after.count;
  const duplicateChanged = before.uniqueCount !== after.uniqueCount;

  if (!countChanged && !duplicateChanged && missing.length === 0 && added.length === 0) {
    return;
  }

  throw new Error(`Release integrity check failed after enrichment. `
    + `before=${before.count}/${before.uniqueCount} after=${after.count}/${after.uniqueCount} `
    + `missing=[${missing.join(', ')}] added=[${added.join(', ')}]. `
    + `The script never intentionally removes or adds releases; restore the DB before continuing.`);
}

function estimateTokens(release, responseReserve) {
  const compact = {
    artist: release.artists_sort,
    title: release.title,
    year: release.year,
    released: release.released,
    country: release.country,
    labels: names(release.labels),
    companies: names(release.companies),
    genres: release.genres || [],
    styles: release.styles || [],
    tracklist: (release.tracklist || []).map(track => ({
      position: track.position,
      title: track.title,
      duration: track.duration,
      artists: names(track.artists),
      extraartists: names(track.extraartists),
    })),
    release_notes: release.notes,
    community_rating: release.community?.rating,
  };
  return Math.max(1, Math.ceil(JSON.stringify(compact).length / 4) + responseReserve);
}

function names(items) {
  return (items || []).map(item => typeof item === 'object' ? item.name : item).filter(Boolean);
}

class SlidingWindowLimiter {
  constructor({ rpm, tpm }) {
    this.rpm = rpm;
    this.tpm = tpm;
    this.windowMs = 60_000;
    this.requests = [];
    this.tokens = [];
    this.lastStart = 0;
    this.minStartGap = Math.ceil(60_000 / rpm);
  }

  async acquire(tokenEstimate) {
    const chargedTokens = Math.min(tokenEstimate, this.tpm);
    while (true) {
      const now = Date.now();
      this.prune(now);
      const requestDelay = this.requests.length < this.rpm ? 0 : this.windowMs - (now - this.requests[0].time) + 5;
      const usedTokens = this.tokens.reduce((sum, item) => sum + item.tokens, 0);
      const tokenDelay = usedTokens + chargedTokens <= this.tpm ? 0 : this.windowMs - (now - this.tokens[0].time) + 5;
      const spacingDelay = Math.max(0, this.minStartGap - (now - this.lastStart));
      const delay = Math.max(requestDelay, tokenDelay, spacingDelay);
      if (delay <= 0) {
        this.requests.push({ time: now });
        this.tokens.push({ time: now, tokens: chargedTokens });
        this.lastStart = now;
        return;
      }
      await sleep(delay);
    }
  }

  prune(now) {
    const keepAfter = now - this.windowMs;
    while (this.requests.length && this.requests[0].time <= keepAfter) this.requests.shift();
    while (this.tokens.length && this.tokens[0].time <= keepAfter) this.tokens.shift();
  }
}

async function enrichRelease(release, options, limiter, stats) {
  const id = releaseId(release);
  const tokenEstimate = estimateTokens(release, options.responseTokenReserve);
  let attempt = 0;

  while (attempt <= options.maxRetries) {
    attempt += 1;
    await limiter.acquire(tokenEstimate);
    try {
      const url = `${options.api}/api/ai/enrich/${encodeURIComponent(id)}${options.force ? '?force=true' : ''}`;
      const response = await fetch(url, { method: 'POST' });
      if (response.ok) {
        stats.enriched += 1;
        return;
      }
      const body = await safeJson(response);
      if (![429, 500, 502, 503, 504].includes(response.status) || attempt > options.maxRetries) {
        stats.failed += 1;
        stats.errors.push({ release_id: id, status: response.status, error: body.error || response.statusText });
        return;
      }
      const retryAfter = retryAfterMs(response) ?? backoffMs(attempt);
      await sleep(retryAfter);
    } catch (error) {
      if (attempt > options.maxRetries) {
        stats.failed += 1;
        stats.errors.push({ release_id: id, error: error.message });
        return;
      }
      await sleep(backoffMs(attempt));
    }
  }
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function retryAfterMs(response) {
  const value = response.headers.get('retry-after');
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, date - Date.now());
}

function backoffMs(attempt) {
  return Math.min(60_000, 1000 * 2 ** (attempt - 1));
}

async function runPool(items, workerCount, worker) {
  let index = 0;
  await Promise.all(Array.from({ length: workerCount }, async () => {
    while (index < items.length) {
      const item = items[index++];
      await worker(item);
    }
  }));
}

function printProgress(stats, total, startedAt) {
  const done = stats.enriched + stats.failed;
  const elapsed = Math.max(1, (Date.now() - startedAt) / 1000);
  const rate = (done / elapsed * 60).toFixed(1);
  process.stdout.write(`\rprocessed ${done}/${total} | enriched ${stats.enriched} | failed ${stats.failed} | ${rate}/min`);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { releases, absolutePath } = await loadReleases(options.db);
  const beforeSnapshot = releaseIdSnapshot(releases);
  const missingId = releases.filter(release => releaseId(release) == null).length;
  const uncached = releases.filter(release => releaseId(release) != null && (options.force || !isCached(release, options.aiVersion)));
  const pending = options.limit === null ? uncached : uncached.slice(0, options.limit);

  const cached = options.force ? 0 : releases.length - uncached.length - missingId;
  const estimatedTokens = pending.reduce((sum, release) => sum + estimateTokens(release, options.responseTokenReserve), 0);
  console.log(`AI enrich collection`);
  console.log(`db: ${absolutePath}`);
  console.log(`api: ${options.api}`);
  console.log(`total releases: ${releases.length} | cached/skipped: ${Math.max(0, cached)} | missing id: ${missingId} | uncached: ${uncached.length} | selected: ${pending.length}`);
  console.log(`limits: ${options.rpm} rpm, ${options.tpm} estimated tpm, concurrency ${options.concurrency}`);
  console.log(`estimated pending tokens: ${estimatedTokens.toLocaleString()}`);

  if (options.dryRun || pending.length === 0) return;

  await verifyApiAvailable(options, pending);
  console.log('api preflight: OK');

  const limiter = new SlidingWindowLimiter(options);
  const stats = { enriched: 0, failed: 0, errors: [] };
  const startedAt = Date.now();
  const progress = setInterval(() => printProgress(stats, pending.length, startedAt), 1000);
  try {
    await runPool(pending, Math.min(options.concurrency, pending.length), release => enrichRelease(release, options, limiter, stats));
  } finally {
    clearInterval(progress);
    printProgress(stats, pending.length, startedAt);
    process.stdout.write('\n');
  }

  const { releases: afterReleases } = await loadReleases(options.db);
  assertReleaseIntegrity(beforeSnapshot, releaseIdSnapshot(afterReleases));
  console.log(`release integrity: OK (${afterReleases.length} releases)`);

  if (stats.errors.length) {
    console.error(JSON.stringify({ errors: stats.errors.slice(0, 50), omitted: Math.max(0, stats.errors.length - 50) }, null, 2));
    process.exitCode = 1;
  }
}

try {
  await main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}