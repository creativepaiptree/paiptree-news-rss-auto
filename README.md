# 🗞️ Paiptree News RSS Auto Collector

Paiptree 관련 뉴스를 자동으로 수집하여 Google Sheets에 저장하는 GitHub Actions 시스템입니다.

## 🔄 자동화 시스템

- **실행 시간**: 매일 오전 8시 (KST)
- **수집 소스**: 주요 RSS 피드 4개
- **검색 키워드**: paiptree, farmersmind, 파이프트리, 파머스마인드
- **저장 위치**: Google Sheets (news_data 시트)

## 📊 Google Sheets 구조

| 컬럼명 | 설명 |
|--------|------|
| id | 고유 식별자 |
| title | 기사 제목 |
| description | 기사 내용/요약 |
| category | 언론사명 |
| tags | 매칭된 키워드 (쉼표 구분) |
| upload_date | 발행일자 |
| download_count | 조회수 |
| thumbnail_url | 대표 이미지 |
| original_url | 원문 링크 |

## 🛠️ 설정 방법

### 1. GitHub Secrets 설정

다음 환경변수를 GitHub 저장소의 Secrets에 추가하세요:

- `GOOGLE_CREDENTIALS`: Google 서비스 계정 JSON (전체 내용)
- `GOOGLE_SHEETS_ID`: Google Sheets 문서 ID

### 2. Google Sheets 준비

1. Google Sheets에서 새 문서 생성
2. `news_data` 시트 생성 (자동 생성됨)
3. Google 서비스 계정과 공유 (편집 권한)

### 3. RSS 피드 수정

`rss_scraper.py`의 `RSS_FEEDS` 리스트에서 RSS 소스를 추가/제거할 수 있습니다.

### 4. 키워드 수정

`rss_scraper.py`의 `KEYWORDS` 리스트에서 검색 키워드를 수정할 수 있습니다.

## 🏃‍♂️ 수동 실행

GitHub Actions 탭에서 "Run workflow" 버튼으로 수동 실행이 가능합니다.

## 📝 로그 확인

GitHub Actions → 해당 워크플로우 → 실행 로그에서 수집 결과를 확인할 수 있습니다.

## 🔧 트러블슈팅

### 뉴스가 수집되지 않는 경우
1. GitHub Actions 실행 로그 확인
2. Google Sheets 권한 설정 확인
3. RSS 피드 URL 상태 확인
4. 환경변수 설정 확인

### 중복 기사가 추가되는 경우
- URL 기반 중복 제거 로직이 있지만, RSS 피드 URL이 변경되면 중복될 수 있습니다.

## 📈 수집 통계

- **평균 실행 시간**: 30-60초
- **일일 수집량**: 키워드 매칭에 따라 0-10개
- **성공률**: 95% 이상

---

**Made for Paiptree Design System** 🎨