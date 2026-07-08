# Paiptree News RSS Auto Agent Rules

Scope: `/Users/zoro/company/paiptree-news-rss-auto`

## Mandatory Start

For any collection, workflow, monitoring, upload, or documentation work, read these first:

1. `/Users/zoro/company/paiptree-news-rss-auto/README.md`
2. `/Users/zoro/vault/_index/map.md`
3. `/Users/zoro/vault/company/systems/paiptree-news-rss-auto-monitoring.md`

For workflow changes, also read:

1. `/Users/zoro/company/paiptree-news-rss-auto/.github/workflows/news.yml`
2. `/Users/zoro/company/paiptree-news-rss-auto/rss_scraper.py`

## Operating Boundary

This repo is the execution engine for Paiptree news RSS collection.

Current baseline:

- GitHub Actions cron is the primary runner.
- Naver News RSS and Google News RSS keyword feeds are the source.
- `dist/news_payload.json` is the scrape success artifact.
- Upload targets `${PAIPTREE_API_URL}/api/batch/collect-news`.
- `NEWS_INGEST_SECRET` is required for API ingestion.
- Hermes is the monitoring/review layer, not the primary runner.

## Success Criteria

Do not treat zero collected articles as failure by itself.

The healthy no-op case is:

```text
payload generated
upload succeeded
0 payload / 0 upsert
```

Treat failures as scrape chain failure, missing payload artifact, upload failure, authentication failure, or workflow/runtime breakage.

## Approval Boundary

Ask before changing GitHub Actions schedules, repository secrets, ingestion target URLs, production upload behavior, Discord/company notification routes, or any DB/API write path.

Do not print secrets or derived secret values. Do not run raw GitHub CLI `gh`; use `/Users/zoro/.local/bin/gh-safe` only after guard verification.

## Verification

For scraper or workflow changes, run the nearest local check first when practical. Use `python3 rss_scraper.py` only when it is safe for the current environment and will not upload to production.

For GitHub workflow state, prefer guarded `gh-safe` checks and report the workflow status without exposing secrets.

