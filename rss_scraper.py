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
import re
from urllib.parse import urlparse
from html import unescape
import dateutil.parser
from difflib import SequenceMatcher

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

# RSS 피드 목록 - Google News 검색 (키워드별)
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=파이프트리&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=파머스마인드&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=paiptree&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=farmersmind&hl=ko&gl=KR&ceid=KR:ko"
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
            worksheet = sheet.add_worksheet(title='news_data', rows=1000, cols=9)
            
            # 9개 컬럼 헤더 추가 (기존 시트 구조에 맞춤)
            headers = [
                'id', 'title', 'description', 'category', 'tags',
                'upload_date', 'download_count', 'thumbnail_url', 'original_url'
            ]
            worksheet.append_row(headers)
            print("✅ news_data 시트 생성 완료")
        
        return worksheet
    except Exception as e:
        print(f"❌ Google Sheets 연결 실패: {e}")
        sys.exit(1)

def extract_domain_name(url):
    """URL에서 도메인명 추출"""
    try:
        domain = urlparse(url).netloc
        # www. 제거 및 첫 번째 도메인만 추출
        domain = re.sub(r'^www\.', '', domain)
        return domain.split('.')[0] if domain else "Unknown"
    except:
        return "Unknown"

def extract_source_from_title(title):
    """제목 끝에서 출처 추출 (- 뒤의 내용)"""
    if ' - ' in title:
        parts = title.rsplit(' - ', 1)  # 마지막 '-' 기준으로 분리
        if len(parts) == 2:
            clean_title = parts[0].strip()
            source = parts[1].strip()
            return clean_title, source
    
    return title, "Unknown"

def clean_source_name(source):
    """출처명 정리 (불필요한 단어 제거)"""
    if not source or source == "Unknown":
        return source
    
    # 자주 나오는 불필요한 단어들 제거
    cleaners = [
        r'\s*뉴스$', r'\s*신문$', r'\s*일보$', 
        r'^\s*', r'\s*$',  # 앞뒤 공백
        r'\.{2,}$'  # 끝의 점들 제거
    ]
    
    clean_source = source
    for cleaner in cleaners:
        clean_source = re.sub(cleaner, '', clean_source)
    
    # 너무 짧거나 비어있으면 원본 사용
    if len(clean_source.strip()) < 2:
        return source
    
    return clean_source.strip()

def extract_publish_date(entry):
    """RSS에서 정확한 발행일 추출"""
    # 우선순위: published_parsed > published > updated_parsed > updated
    for date_field in ['published_parsed', 'updated_parsed']:
        if hasattr(entry, date_field) and entry.get(date_field):
            try:
                return datetime(*entry[date_field][:6])
            except:
                continue
    
    # 문자열 날짜 파싱 시도
    for date_field in ['published', 'updated']:
        if entry.get(date_field):
            try:
                return dateutil.parser.parse(entry[date_field])
            except:
                continue
    
    print("⚠️ 날짜 정보 없음, 현재 시간 사용")
    return datetime.now()

def clean_description(raw_description):
    """HTML 태그 제거하고 깔끔한 한글 내용만 추출"""
    if not raw_description:
        return "뉴스 내용은 원문 링크에서 확인하세요"
    
    # HTML 태그 제거
    clean_text = re.sub(r'<[^>]+>', '', raw_description)
    
    # HTML 엔티티 디코딩 (&lt; &gt; &amp; 등)
    clean_text = unescape(clean_text)
    
    # 연속된 공백/줄바꿈 정리
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # 특수문자 정리 (한글, 영문, 숫자, 기본 문장부호만 유지)
    clean_text = re.sub(r'[^\w\s\.\,\!\?\:\;\(\)\-\'\"…]', '', clean_text, flags=re.UNICODE)
    
    # 빈 내용 체크
    if not clean_text or len(clean_text.strip()) < 10:
        return "뉴스 내용은 원문 링크에서 확인하세요"
    
    return clean_text[:500]

def categorize_news(title, description, source):
    """키워드 기반 카테고리 자동 분류"""
    content = f"{title} {description}".lower()
    
    # 카테고리 키워드 매핑
    categories = {
        '경제/투자': ['투자', '펀딩', '투자금', '시리즈', '기업공개', '상장', '매출', '수익', '자금조달', '그린랩스'],
        '기술/AI': ['ai', '인공지능', '스마트팜', '플랫폼', '기술', '솔루션', '시스템', '파머스마인드', 'farmersmind'],
        '사업확장': ['진출', '협력', '업무협약', '파트너십', '확장', '글로벌', 'cpf', '토자이', '한호운수'],
        '농축산업': ['양계', '축산', '농가', '조류독감', '질병예찰', '생계물류', '육계시장', '관제시스템'],
        '언론/인터뷰': ['인터뷰', '대표', '창업자', 'ceo', '스타트업', '공동대표'],
        '행사/전시': ['afro', '전시', '컨퍼런스', '세미나', '발표', '소개'],
        '연구개발': ['건국대', '연구', '개발', '공동연구', '대학', '학술'],
    }
    
    for category, keywords in categories.items():
        if any(keyword in content for keyword in keywords):
            return category
    
    return '기타뉴스'

def calculate_similarity(title1, title2):
    """두 제목의 유사도 계산 (0~1)"""
    # 공백과 특수문자 제거 후 비교
    clean_title1 = re.sub(r'[^\w]', '', title1, flags=re.UNICODE)
    clean_title2 = re.sub(r'[^\w]', '', title2, flags=re.UNICODE)
    
    return SequenceMatcher(None, clean_title1, clean_title2).ratio()

def deduplicate_news_comprehensive(all_news_items):
    """제목 유사도 + URL 기반 종합 중복 제거"""
    unique_news = []
    seen_titles = []
    seen_urls = set()
    
    print(f"🔍 중복 제거 시작: {len(all_news_items)}개 뉴스 처리 중...")
    
    for news in all_news_items:
        title = news['title'].lower().strip()
        clean_url = news['original_url'].split('?')[0]  # URL 파라미터 제거
        
        # URL 중복 체크
        if clean_url in seen_urls:
            print(f"🔄 중복 URL 제거: {title[:50]}...")
            continue
        
        # 제목 유사도 체크 (85% 이상 유사하면 중복으로 판단)
        is_similar = False
        for seen_title in seen_titles:
            similarity = calculate_similarity(title, seen_title)
            if similarity > 0.85:
                print(f"🔄 유사 제목 제거: {title[:50]}... (유사도: {similarity:.2f})")
                is_similar = True
                break
        
        if not is_similar:
            seen_titles.append(title)
            seen_urls.add(clean_url)
            unique_news.append(news)
            print(f"✅ 고유 뉴스 추가: {title[:50]}...")
    
    print(f"📊 중복 제거 완료: {len(unique_news)}개 남음 ({len(all_news_items) - len(unique_news)}개 제거)")
    return unique_news

def fetch_rss_news(rss_url, keywords, initial_mode=False):
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
                pub_datetime = extract_publish_date(entry)
                if pub_datetime >= seven_days_ago:
                    recent_entries.append(entry)
            entries_to_process = recent_entries
            print(f"🗓️ 최근 7일 이내 뉴스: {len(entries_to_process)}개")
        else:
            print(f"🎯 초기 수집 모드: 모든 가능한 뉴스 ({len(entries_to_process)}개) 처리")
        
        # 각 뉴스 아이템 확인
        for entry in entries_to_process:
            original_title = entry.get('title', '')
            raw_description = entry.get('description', '') or entry.get('summary', '')
            link = entry.get('link', '')
            
            # 🔥 제목에서 출처 추출
            clean_title, source = extract_source_from_title(original_title)
            source = clean_source_name(source)
            
            # URL에서 도메인 추출 (출처 없을 경우 대안)
            if source == "Unknown":
                source = extract_domain_name(link)
            
            # 키워드 매칭 확인 (깔끔한 제목으로)
            content_to_check = f"{clean_title} {raw_description}".lower()
            matched_keywords = [kw for kw in keywords if kw.lower() in content_to_check]
            
            if matched_keywords:
                # 정확한 발행일자 추출
                pub_datetime = extract_publish_date(entry)
                pub_date = pub_datetime.strftime('%Y-%m-%d')
                
                # HTML 태그 제거한 깔끔한 설명
                clean_desc = clean_description(raw_description)
                
                # 썸네일 이미지 추출 시도
                thumbnail_url = ""
                if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                    thumbnail_url = entry.media_thumbnail[0].get('url', '')
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if hasattr(enc, 'type') and enc.type.startswith('image/'):
                            thumbnail_url = enc.href
                            break
                
                # 썸네일이 없으면 기본 이미지
                if not thumbnail_url:
                    thumbnail_url = "https://via.placeholder.com/300x200/00B0EB/FFFFFF?text=Paiptree+News"
                
                news_item = {
                    'title': clean_title[:200] if clean_title else "제목 없음",  # 출처 제거된 깔끔한 제목
                    'description': clean_desc,
                    'category': source,  # 실제 언론사명 (매일경제, 머니투데이 등)
                    'tags': ','.join(matched_keywords),
                    'upload_date': pub_date,  # 실제 뉴스 발행일
                    'pub_datetime': pub_datetime,  # 정렬용
                    'download_count': 0,
                    'thumbnail_url': thumbnail_url,
                    'original_url': link
                }
                
                news_items.append(news_item)
                print(f"✅ 키워드 매칭: {clean_title[:50]}... (출처: {source}) [{pub_date}]")
        
        print(f"📊 {rss_url}에서 {len(news_items)}개 매칭 뉴스 발견")
        return news_items
        
    except Exception as e:
        print(f"❌ RSS 피드 처리 실패 {rss_url}: {e}")
        return []

def generate_simple_id():
    """간단한 타임스탬프 기반 ID 생성 (API 호출 없음)"""
    timestamp = int(time.time())
    return f"{timestamp % 100000:05d}"

def add_news_to_sheet(worksheet, news_item):
    """Google Sheets에 뉴스 추가 - 9개 컬럼 버전"""
    try:
        # 간단한 ID 생성 (API 호출 없음)
        news_id = generate_simple_id()
        
        # 9개 컬럼에 맞춘 데이터 생성
        row_data = [
            news_id,                        # A: id
            news_item['title'],             # B: title (출처 제거된 깔끔한 제목)
            news_item['description'],       # C: description (HTML 태그 제거됨)
            news_item['category'],          # D: category (실제 언론사명)
            news_item['tags'],              # E: tags
            news_item['upload_date'],       # F: upload_date (실제 뉴스 날짜)
            news_item['download_count'],    # G: download_count
            news_item['thumbnail_url'],     # H: thumbnail_url
            news_item['original_url']       # I: original_url
        ]
        
        worksheet.append_row(row_data)
        print(f"✅ 뉴스 추가 (ID: {news_id}): {news_item['title'][:50]}...")
        
        # API 호출 제한 고려하여 여유롭게 대기 (3초)
        time.sleep(3.0)
        return True
        
    except Exception as e:
        print(f"❌ 뉴스 추가 실패, 스킵: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 Paiptree 뉴스 수집 시작 (출처 추출 버전)")
    print(f"📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 초기 수집 모드 확인 (환경변수)
    initial_mode = os.environ.get('INITIAL_COLLECTION', 'false').lower() == 'true'
    
    if initial_mode:
        print("🎯 초기 대량 수집 모드 활성화")
        print("📚 가능한 모든 과거 뉴스 수집 중...")
    else:
        print("📅 일반 모드: 최근 7일 이내 뉴스만 수집")
    
    print("🔧 개선사항: 정확한 날짜, HTML 제거, 실제 출처 카테고리, 중복 제거")
    
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
    
    # 모든 RSS에서 뉴스 수집
    for rss_url in RSS_FEEDS:
        news_items = fetch_rss_news(rss_url, KEYWORDS, initial_mode)
        total_found += len(news_items)
        all_news_items.extend(news_items)
    
    print(f"\n📊 수집 전 총 뉴스: {len(all_news_items)}개")
    
    # 🔥 중복 제거 처리
    unique_news = deduplicate_news_comprehensive(all_news_items)
    
    print(f"✅ 중복 제거 후: {len(unique_news)}개")
    print(f"🗑️ 제거된 중복: {len(all_news_items) - len(unique_news)}개")
    
    # 발행일자 기준으로 정렬 (오래된 것부터)
    unique_news.sort(key=lambda x: x.get('pub_datetime', datetime.now()))
    
    print(f"\n📊 총 {len(unique_news)}개 고유 뉴스를 시간순으로 추가 중...")
    print("⏰ 각 뉴스마다 3초씩 대기하여 안전하게 처리합니다...")
    
    # 시트에 추가
    for i, news_item in enumerate(unique_news, 1):
        print(f"📝 진행률: {i}/{len(unique_news)}")
        if add_news_to_sheet(worksheet, news_item):
            total_collected += 1
    
    # 실행 결과
    end_time = time.time()
    execution_time = round(end_time - start_time, 2)
    
    print(f"\n🎉 뉴스 수집 완료!")
    print(f"🎯 수집 모드: {'초기 대량 수집' if initial_mode else '일반 수집'}")
    print(f"📊 총 발견: {total_found}개")
    print(f"🔄 중복 제거: {len(all_news_items) - len(unique_news)}개")
    print(f"✅ 고유 뉴스 추가: {total_collected}개")
    print(f"⏱️ 실행 시간: {execution_time}초")
    print(f"🔧 개선된 기능: 정확한 날짜, 깔끔한 설명, 실제 언론사 카테고리, 스마트 중복 제거")
    
    if total_collected == 0:
        print("ℹ️ 새로운 뉴스가 없습니다.")
    else:
        print(f"🌟 {total_collected}개의 고유한 뉴스가 추가되었습니다!")
        print("📰 카테고리: 실제 언론사명 (매일경제, 머니투데이 등)")

if __name__ == "__main__":
    main()
