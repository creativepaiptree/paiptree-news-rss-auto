# 🗞️ Paiptree News RSS Auto Collector

Paiptree 관련 뉴스를 정기 수집해 payload로 정규화한 뒤, Paiptree API를 통해 DB에 적재하는 GitHub Actions 기반 수집 작업입니다.

## 현재 운영 원칙

- 본선 실행 주체: GitHub Actions cron
- 수집 대상: Naver News RSS + Google News RSS 키워드 검색 결과
- 적재 대상: `PAIPTREE_API_URL` 뒤의 뉴스 수집 API (`/api/batch/collect-news`)
- 인증 방식: `NEWS_INGEST_SECRET` 헤더 기반 서버 검증
- 운영 알림 방향:
  - 현재: GitHub Actions → Discord webhook
  - 전환 목표: Discord 알림 중지, Hermes cron이 진행상황/실패 여부를 감시·보고

## 🔄 자동화 시스템

- 실행 시간: 매일 오전 8시 (KST) = UTC 23:00
- 수집 소스: 주요 RSS 피드 8개
  - 네이버 뉴스 RSS 4개
  - Google News RSS 4개
- 검색 키워드: `paiptree`, `farmersmind`, `파이프트리`, `파머스마인드`
- 결과 산출물:
  - `dist/news_payload.json`
  - `news_data.csv`
- 업로드 흐름:
  - RSS 수집 → payload 생성 → Paiptree API 업로드 → 결과 기록

## ✨ 주요 기능

- 뉴스 수집: RSS 피드에서 Paiptree 관련 기사 자동 수집
- 데이터 정제: HTML 제거, 설명 정리, 언론사 표기 정돈
- 중복 방지: 기사 `original_url` 기준 dedupe
- 안정 ID 부여: `news_<sha1>` 형식의 stable id 생성
- DB 적재: API 업로드로 DB upsert 수행
- 배치 운영: GitHub Actions 스케줄 및 수동 실행 지원

## 실제 운영 구조

### 정기 수집 워크플로우
- 파일: `.github/workflows/news.yml`
- 역할:
  1. Python 환경 준비
  2. `rss_scraper.py` 실행
  3. `dist/news_payload.json` 생성
  4. `PAIPTREE_API_URL/api/batch/collect-news` 로 업로드
  5. 결과 요약 기록

### 초기/대량 수집 워크플로우
- 파일: `.github/workflows/initial-collection.yml`
- 역할:
  - 초기 적재나 최근 적재를 수동 실행으로 수행
  - news/social payload를 생성해 같은 API로 업로드

## GitHub Actions Secrets

현재 운영 기준으로 핵심 Secret은 아래입니다.

- `PAIPTREE_API_URL`
  - 뉴스 payload를 업로드할 Paiptree API 기본 주소
- `NEWS_INGEST_SECRET`
  - `/api/batch/collect-news` 업로드용 인증 헤더 값
- `DISCORD_WEBHOOK_URL`
  - 현재는 사용 중이지만, 향후 운영 중지 대상

주의:
- README의 예전 Google Sheets 저장 설명은 더 이상 본선 운영 기준이 아닙니다.
- Google 관련 의존성과 보조 스크립트는 과거 구조 흔적으로 남아 있을 수 있으며, 실제 본선은 API 업로드 기준입니다.

## Company GitHub Guard

- 이 프로젝트는 `repo-guard.config.json` 에 필수 원격을 선언합니다.
- push 전에는 `python3 scripts/github_repo_guard.py` 로 검증합니다.
- guard 체크 항목:
  - `origin` 이 `creativepaiptree/paiptree-news-rss-auto` 인지
  - 현재 `gh` 계정이 `WRITE` 이상인지

## 운영 방향 메모

현재 결정된 방향:
- 수집 실행 자체는 GitHub cron 유지
- Discord 운영 알림은 중지 방향
- Hermes cron은 아래 역할로 붙이는 방향 검토
  - 실행 성공/실패 점검
  - 최근 적재 건수 이상 여부 점검
  - 필요 시 회사 채널/운영 루틴으로 보고

즉, 이 저장소는 당분간 “실행 엔진” 역할을 유지하고, Hermes는 “운영 감시/리뷰 계층”으로 추가됩니다.

## 수동 실행

- GitHub Actions 탭에서 `Paiptree News Collector` 워크플로우를 수동 실행 가능
- 초기 적재가 필요하면 `📚 Paiptree News Initial Collection` 워크플로우를 별도로 실행

## 로그 확인

- GitHub Actions 실행 로그에서 수집/업로드 단계별 상태 확인 가능
- 향후 Hermes 점검 cron을 붙이면 GitHub 실행 결과를 별도 운영 보고로 요약 가능

---

Made for Paiptree operations
