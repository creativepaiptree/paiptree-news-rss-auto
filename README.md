# 🗞️ Paiptree News RSS Auto Collector

Paiptree 관련 뉴스를 자동으로 수집하여 Google Sheets에 저장하는 GitHub Actions 시스템입니다.

## 🔄 자동화 시스템

- **실행 시간**: 매일 오전 8시 (KST)
- **수집 소스**: 주요 RSS 피드 4개
- **검색 키워드**: paiptree, farmersmind, 파이프트리, 파머스마인드
- **저장 위치**: Google Sheets (`news_data` 시트)
- **실행 결과**: 성공/실패 시 Discord 알림

## ✨ 주요 기능

- **뉴스 수집**: 네이버 뉴스 RSS 피드에서 키워드로 뉴스를 자동 수집합니다.
- **데이터 정제**: 기사 내용에서 불필요한 HTML 태그와 중복되는 언론사명을 제거합니다.
- **중복 방지**: 기사 원문 URL을 기반으로 중복 수집을 방지합니다.
- **데이터 저장**: 수집된 데이터를 Google Sheets에 자동으로 추가합니다.
- **자동화 및 알림**: GitHub Actions으로 매일 작업을 실행하고, 결과를 Discord로 알려줍니다.

## 🛠️ 설정 방법

### 1. GitHub Secrets 설정

다음 환경변수를 GitHub 저장소의 `Settings > Secrets and variables > Actions`에 추가하세요.

- `GOOGLE_CREDENTIALS`: Google 서비스 계정의 JSON 키 전체 내용
- `GOOGLE_SHEETS_ID`: 데이터를 저장할 Google Sheets 문서의 ID
- `DISCORD_WEBHOOK_URL`: 실행 결과를 알림받을 Discord 채널의 웹훅 URL

### 2. Google Sheets 및 서비스 계정 준비

1.  Google Cloud Console에서 서비스 계정을 생성하고, **Google Sheets API**와 **Google Drive API**를 활성화합니다.
2.  서비스 계정 키(JSON)를 다운로드하여 `GOOGLE_CREDENTIALS` Secret 값으로 저장합니다.
3.  새 Google Sheets 문서를 만들고, 이 문서의 ID를 `GOOGLE_SHEETS_ID` Secret 값으로 저장합니다.
4.  해당 Google Sheets 문서를 서비스 계정의 이메일 주소와 **편집자(Editor) 권한**으로 공유합니다.
5.  `news_data` 시트는 스크립트 최초 실행 시 자동으로 생성됩니다.

### 3. 스크립트 수정 (선택 사항)

- **RSS 피드 변경**: `rss_scraper.py`의 `RSS_FEEDS` 리스트를 수정하여 수집 소스를 변경할 수 있습니다.
- **검색 키워드 변경**: `rss_scraper.py`의 `KEYWORDS` 리스트를 수정하여 검색어를 변경할 수 있습니다.

## 🏃‍♂️ 수동 실행

GitHub Actions 탭의 `Paiptree News Collector` 워크플로우에서 `Run workflow` 버튼으로 언제든지 수동 실행이 가능합니다.

## 📝 로그 확인

GitHub Actions의 워크플로우 실행 로그에서 각 단계별 상세한 수집 결과를 확인할 수 있습니다.

---

**Made for Paiptree Design System** 🎨
