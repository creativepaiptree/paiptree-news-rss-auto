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

## 🆕 최신 기능: 고급 이미지 처리 시스템

### 이미지 처리 파이프라인
- **웹 스크래핑**: 기사에서 첫 번째 의미있는 이미지 추출
- **이미지 최적화**: 다운로드, 리사이징, 압축 처리
- **Google Drive 업로드**: 최적화된 이미지를 Google Drive에 업로드
- **공개 링크 생성**: 웹에서 접근 가능한 공개 URL 생성

### 이미지 추출 우선순위
1. **og:image 메타 태그** (가장 우선)
2. **기사 내 첫 번째 이미지** (100x100 이상)
3. **기타 이미지** (fallback)

### 이미지 최적화 설정
- **최대 크기**: 400x300 픽셀
- **품질**: 85% JPEG
- **포맷**: JPEG (알파 채널 자동 변환)

## 주요 기능

### 📰 뉴스 수집
- Google News RSS 피드 모니터링
- 파이프트리 관련 키워드 자동 필터링
- 중복 제거 및 유사도 검사
- 정확한 발행일자 추출

### 🏷️ 태그 시스템
- 제목과 본문에서 교차 키워드 추출
- 우선순위 키워드 시스템
- 의미있는 태그 자동 생성

### 📊 데이터 관리
- Google Sheets 자동 업데이트
- 9개 컬럼 구조 (id, title, description, category, tags, upload_date, download_count, thumbnail_url, original_url)
- API 호출 제한 고려한 안전한 처리

## 설치 및 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
export GOOGLE_CREDENTIALS='{"type": "service_account", ...}'
export GOOGLE_SHEETS_ID='your-sheets-id'
export INITIAL_COLLECTION='false'  # true: 초기 대량 수집, false: 최근 7일
```

### 3. Google Service Account 설정
- Google Cloud Console에서 서비스 계정 생성
- Google Sheets API 및 Google Drive API 활성화
- 서비스 계정 키 JSON 다운로드
- 환경변수에 JSON 내용 설정

## 사용법

### 일반 실행
```bash
python rss_scraper.py
```

### 초기 대량 수집
```bash
export INITIAL_COLLECTION='true'
python rss_scraper.py
```

### 이미지 처리 파이프라인 테스트
```bash
python test_image_pipeline.py
```

## GitHub Actions 자동화

### 스케줄링
- **일반 모드**: 매일 오전 9시 실행 (최근 7일 뉴스)
- **초기 모드**: 수동 트리거 (모든 과거 뉴스)

### 워크플로우 파일
- `.github/workflows/rss-scraper.yml`

## 데이터 구조

### Google Sheets 컬럼
| 컬럼 | 설명 | 예시 |
|------|------|------|
| A | id | 고유 ID |
| B | title | 뉴스 제목 |
| C | description | 뉴스 설명 |
| D | category | 언론사명 |
| E | tags | 키워드 태그 |
| F | upload_date | 발행일자 |
| G | download_count | 다운로드 수 |
| H | thumbnail_url | 썸네일 이미지 URL |
| I | original_url | 원문 링크 |

## 개선사항

### 최신 업데이트
- ✅ 정확한 발행일자 추출
- ✅ HTML 태그 제거
- ✅ 실제 언론사명 카테고리
- ✅ 제목+본문 교차 키워드 태그
- ✅ 종합적 중복 제거
- ✅ 고급 이미지 처리 시스템

### 이미지 처리 개선
- ✅ 웹 스크래핑으로 기사 이미지 추출
- ✅ 이미지 최적화 및 압축
- ✅ Google Drive 자동 업로드
- ✅ 공개 접근 가능한 URL 생성

## 문제 해결

### 일반적인 문제
1. **Google API 할당량 초과**: 실행 간격 조정
2. **네트워크 오류**: 재시도 로직으로 자동 처리
3. **이미지 처리 실패**: 기본 이미지로 fallback

### 로그 확인
- 상세한 진행 상황 로그 출력
- 각 단계별 성공/실패 표시
- 오류 발생 시 구체적인 원인 표시

## 라이선스

이 프로젝트는 파이프트리 내부 사용을 위한 프로젝트입니다.

---

**Made for Paiptree Design System** 🎨