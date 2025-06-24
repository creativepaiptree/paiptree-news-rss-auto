#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import time
import hashlib
import requests
from datetime import datetime, timedelta
import sys
from web_scraper import ArticleImageScraper

# 환경변수에서 설정 읽기
def get_config():
    """환경변수에서 설정 정보 읽기"""
    try:
        # Google Sheets 인증 정보
        google_creds = os.environ.get('GOOGLE_CREDENTIALS')
        if not google_creds:
            raise ValueError("GOOGLE_CREDENTIALS 환경변수가 설정되지 않았습니다.")
        
        # JSON 파싱 (환경변수는 이미 JSON 문자열)
        try:
            creds_dict = json.loads(google_creds)
            print("✅ Google Credentials JSON 파싱 성공")
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {e}")
            print(f"📝 받은 데이터 길이: {len(google_creds)} 문자")
            print(f"📝 데이터 시작 부분: {google_creds[:100]}...")
            raise ValueError(f"GOOGLE_CREDENTIALS JSON 파싱 실패: {e}")
        
        # Google Sheets ID
        sheets_id = os.environ.get('GOOGLE_SHEETS_ID')
        if not sheets_id:
            raise ValueError("GOOGLE_SHEETS_ID 환경변수가 설정되지 않았습니다.")
        
        print(f"✅ Google Sheets ID: {sheets_id[:20]}...")
        return creds_dict, sheets_id
        
    except Exception as e:
        print(f"❌ 설정 읽기 실패: {e}")
        sys.exit(1)

# RSS 피드 목록 - 네이버 뉴스 검색 (키워드별)
RSS_FEEDS = [
    "http://newssearch.naver.com/search.naver?where=rss&query=파이프트리",
    "http://newssearch.naver.com/search.naver?where=rss&query=파머스마인드", 
    "http://newssearch.naver.com/search.naver?where=rss&query=paiptree",
    "http://newssearch.naver.com/search.naver?where=rss&query=farmersmind"
]

# 검색 키워드 (이미 RSS에서 필터링되므로 전체 매칭)
KEYWORDS = [
    "파이프트리", "파머스마인드", "paiptree", "farmersmind"
]

def setup_google_sheets(creds_dict, sheets_id):
    """Google Sheets 연결 설정"""
    try:
        print("🔗 Google Sheets 연결 중...")
        
        # 인증 범위 설정
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # 서비스 계정 인증
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(credentials)
        
        # 스프레드시트 열기
        sheet = gc.open_by_key(sheets_id)
        
        # news_data 워크시트 가져오기 또는 생성
        try:
            worksheet = sheet.worksheet('news_data')
            print("✅ 기존 news_data 시트 발견")
        except gspread.WorksheetNotFound:
            print("📝 news_data 시트 생성 중...")
            worksheet = sheet.add_worksheet(title='news_data', rows=1000, cols=21)
            
            # Materials 표준 21개 컬럼 (A-U) 헤더 추가
            headers = [
                'id', 'title', 'description', 'category', 'tags',                    # A-E
                'upload_date', 'file_size', 'file_format', 'dimensions',             # F-I
                'creator', 'brand_alignment', 'usage_rights', 'version',             # J-M
                'download_count', 'rating', 'thumbnail_url', 'file_url',            # N-Q
                'original_url', 'status', 'featured', 'created_at'                  # R-U
            ]
            worksheet.append_row(headers)
            print("✅ news_data 시트 생성 완료")
        
        return worksheet
    except Exception as e:
        print(f"❌ Google Sheets 연결 실패: {e}")
        sys.exit(1)

def fetch_rss_news(rss_url, keywords, image_scraper, initial_mode=False):
    """RSS 피드에서 뉴스 가져오기"""
    news_items = []
    
    try:
        print(f"📡 RSS 피드 확인 중: {rss_url}")
        
        # RSS 피드 파싱
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            print(f"⚠️ RSS 피드 파싱 경고: {rss_url}")
        
        total_entries = len(feed.entries) if hasattr(feed, 'entries') else 0
        print(f"📊 총 {total_entries}개 RSS 엔트리 발견")
        
        # 초기 모드일 때는 모든 뉴스 수집, 일반 모드일 때는 최근 뉴스만
        entries_to_process = feed.entries if hasattr(feed, 'entries') else []
        
        if not initial_mode:
            # 일반 모드: 최근 7일 이내 뉴스만
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_entries = []
            for entry in entries_to_process:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                    if pub_date >= seven_days_ago:
                        recent_entries.append(entry)
                else:
                    # 날짜 정보가 없으면 최근으로 간주
                    recent_entries.append(entry)
            entries_to_process = recent_entries
            print(f"🗓️ 최근 7일 이내 뉴스: {len(entries_to_process)}개")
        else:
            print(f"🎯 초기 수집 모드: 모든 가능한 뉴스 ({len(entries_to_process)}개) 처리")
        
        # 각 뉴스 아이템 확인
        for entry in entries_to_process:
            title = entry.get('title', '')
            description = entry.get('description', '') or entry.get('summary', '')
            link = entry.get('link', '')
            
            # 키워드 매칭 확인
            content_to_check = f"{title} {description}".lower()
            matched_keywords = [kw for kw in keywords if kw.lower() in content_to_check]
            
            if matched_keywords:
                # 발행일자 처리
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6]).strftime('%Y-%m-%d')
                    pub_datetime = datetime(*published[:6])
                else:
                    pub_date = datetime.now().strftime('%Y-%m-%d')
                    pub_datetime = datetime.now()
                
                # 언론사명 추출
                source = feed.feed.get('title', 'Unknown')
                
                # 🔥 썸네일 이미지 추출 시도 (RSS → 원본 기사 → 기본 이미지)
                thumbnail_url = ""
                
                # 1. RSS에서 제공하는 이미지 우선 시도
                if hasattr(entry, 'media_thumbnail'):
                    thumbnail_url = entry.media_thumbnail[0]['url'] if entry.media_thumbnail else ""
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.type.startswith('image/'):
                            thumbnail_url = enc.href
                            break
                
                # 2. RSS 이미지가 없으면 원본 기사에서 추출 🔥
                if not thumbnail_url and link:
                    try:
                        print(f"🖼️ 원본 기사 이미지 추출 시도: {link}")
                        # 🔥 최적화된 이미지 추출 (400x300 최대 크기)
                        extracted_image = image_scraper.extract_largest_image(
                            link, 
                            max_size=(400, 300),  # 썸네일용 최적 크기
                            return_optimized=True  # 압축 및 리사이징 활성화
                        )
                        if extracted_image:
                            thumbnail_url = extracted_image
                            print(f"✅ 최적화된 이미지 추출 성공!")
                            if extracted_image.startswith('data:image/'):
                                print(f"📁 Base64 인코딩된 이미지 ({len(extracted_image)} 문자)")
                            else:
                                print(f"🔗 원본 URL: {extracted_image}")
                        else:
                            print(f"❌ 원본 기사 이미지 추출 실패: {link}")
                    except Exception as e:
                        print(f"⚠️ 이미지 추출 예외: {e}")
                
                # 3. 여전히 없으면 키워드별 기본 이미지
                if not thumbnail_url:
                    thumbnail_url = get_default_image_by_keywords(matched_keywords)
                
                news_item = {
                    'title': title[:200],  # 제목 길이 제한
                    'description': description[:500],  # 설명 길이 제한
                    'category': source,
                    'tags': ','.join(matched_keywords),
                    'upload_date': pub_date,
                    'pub_datetime': pub_datetime,  # 정렬용
                    'download_count': 0,  # 기본값 0
                    'thumbnail_url': thumbnail_url,
                    'original_url': link
                }
                
                news_items.append(news_item)
                print(f"✅ 키워드 매칭: {title[:50]}... (키워드: {matched_keywords}) [{pub_date}]")
        
        print(f"📊 {rss_url}에서 {len(news_items)}개 매칭 뉴스 발견")
        return news_items
        
    except Exception as e:
        print(f"❌ RSS 피드 처리 실패 {rss_url}: {e}")
        return []

def generate_sequential_id(worksheet):
    """기존 데이터 확인해서 다음 번호 생성 (001, 002, 003...)"""
    try:
        all_records = worksheet.get_all_records()
        if not all_records:
            return "001"
        
        # 기존 ID에서 숫자 추출해서 최대값 찾기
        max_num = 0
        for record in all_records:
            try:
                current_id = str(record.get('id', '0'))
                # 숫자만 추출 (앞의 0 제거)
                num = int(current_id.lstrip('0')) if current_id.strip() else 0
                max_num = max(max_num, num)
            except (ValueError, TypeError):
                continue
        
        # 다음 번호를 3자리로 포맷팅
        next_num = max_num + 1
        return f"{next_num:03d}"
        
    except Exception as e:
        print(f"⚠️ ID 생성 실패, 임시 ID 사용: {e}")
        # 실패시 타임스탬프 기반 ID
        return f"{int(time.time() % 10000):04d}"

def is_duplicate_news(worksheet, original_url):
    """중복 뉴스 확인 (URL 기반)"""
    try:
        # 모든 기존 데이터 가져오기
        all_records = worksheet.get_all_records()
        
        for record in all_records:
            # URL이 일치하면 중복
            if record.get('original_url') == original_url:
                return True
        
        return False
    except Exception as e:
        print(f"⚠️ 중복 확인 실패: {e}")
        return False

def get_default_image_by_keywords(matched_keywords):
    """키워드별 기본 이미지 URL 반환"""
    # 키워드별 고품질 기본 이미지 매핑
    default_images = {
        'paiptree': 'https://example.com/paiptree-logo.jpg',
        'farmersmind': 'https://example.com/farmersmind-logo.jpg',
        '파이프트리': 'https://example.com/paiptree-kr.jpg',
        '파머스마인드': 'https://example.com/farmersmind-kr.jpg'
    }
    
    # 매칭된 키워드 중 첫 번째로 기본 이미지 선택
    for keyword in matched_keywords:
        if keyword.lower() in default_images:
            return default_images[keyword.lower()]
    
    # 매칭되는 기본 이미지가 없으면 빈 문자열
    return ""

def add_news_to_sheet(worksheet, news_item):
    """Google Sheets에 뉴스 추가"""
    try:
        # 중복 확인 (URL 기반)
        if is_duplicate_news(worksheet, news_item['original_url']):
            print(f"⏭️ 중복 뉴스 스킵: {news_item['title'][:50]}...")
            return False
        
        # 순차 ID 생성
        news_id = generate_sequential_id(worksheet)
        
        # Materials 표준 21개 컬럼에 맞춘 데이터 생성
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        row_data = [
            news_id,                                    # A: id
            news_item['title'],                         # B: title
            news_item['description'],                   # C: description
            news_item['category'],                      # D: category (언론사)
            news_item['tags'],                          # E: tags
            news_item['upload_date'],                   # F: upload_date
            'N/A',                                      # G: file_size (뉴스는 파일 아님)
            'news',                                     # H: file_format (뉴스 타입)
            'N/A',                                      # I: dimensions
            news_item['category'],                      # J: creator (언론사명)
            'high',                                     # K: brand_alignment (브랜드 연관도 높음)
            'read-only',                               # L: usage_rights (읽기전용)
            '1.0',                                      # M: version
            news_item['download_count'],                # N: download_count
            '0',                                        # O: rating (기본 0점)
            news_item['thumbnail_url'],                 # P: thumbnail_url
            news_item['original_url'],                  # Q: file_url (원문 링크)
            news_item['original_url'],                  # R: original_url (동일)
            'active',                                   # S: status (활성 상태)
            'false',                                    # T: featured (기본 비추천)
            current_time                                # U: created_at (생성시간)
        ]
        
        worksheet.append_row(row_data)
        print(f"✅ 뉴스 추가 (ID: {news_id}): {news_item['title'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ 뉴스 추가 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 Paiptree 뉴스 수집 시작")
    print(f"📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 초기 수집 모드 확인 (환경변수)
    initial_mode = os.environ.get('INITIAL_COLLECTION', 'false').lower() == 'true'
    
    if initial_mode:
        print("🎯 초기 대량 수집 모드 활성화")
        print("📚 가능한 모든 과거 뉴스 수집 중...")
    else:
        print("📅 일반 모드: 최근 7일 이내 뉴스만 수집")
    
    start_time = time.time()
    
    # 설정 읽기
    creds_dict, sheets_id = get_config()
    
    # Google Sheets 연결
    worksheet = setup_google_sheets(creds_dict, sheets_id)
    
    # 뉴스 수집
    total_collected = 0
    total_found = 0
    all_news_items = []
    
    print(f"🔍 {len(RSS_FEEDS)}개 RSS 피드에서 뉴스 검색 중...")
    print(f"🏷️ 검색 키워드: {', '.join(KEYWORDS)}")
    
    # 🔥 이미지 스크래퍼 초기화
    print("🖼️ 이미지 스크래퍼 초기화 중...")
    image_scraper = ArticleImageScraper(timeout=10, max_retries=2)
    
    for rss_url in RSS_FEEDS:
        news_items = fetch_rss_news(rss_url, KEYWORDS, image_scraper, initial_mode)
        total_found += len(news_items)
        all_news_items.extend(news_items)
    
    # 발행일자 기준으로 정렬 (오래된 것부터)
    all_news_items.sort(key=lambda x: x.get('pub_datetime', datetime.now()))
    
    print(f"\n📊 총 {len(all_news_items)}개 뉴스를 시간순으로 정렬하여 추가 중...")
    
    # 시트에 추가
    for news_item in all_news_items:
        if add_news_to_sheet(worksheet, news_item):
            total_collected += 1
        
        # API 호출 제한 고려하여 잠시 대기
        time.sleep(0.5)
    
    # 실행 결과
    end_time = time.time()
    execution_time = round(end_time - start_time, 2)
    
    print(f"\n🎉 뉴스 수집 완료!")
    print(f"🎯 수집 모드: {'초기 대량 수집' if initial_mode else '일반 수집'}")
    print(f"📊 총 발견: {total_found}개")
    print(f"✅ 새로 추가: {total_collected}개")
    print(f"⏱️ 실행 시간: {execution_time}초")
    
    if total_collected == 0:
        print("ℹ️ 새로운 뉴스가 없습니다.")
    else:
        print(f"🌟 {total_collected}개의 새로운 뉴스가 추가되었습니다!")

if __name__ == "__main__":
    main()
