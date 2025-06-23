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
                
                # 언론사명 추출 (개선된 버전)
                source = feed.feed.get('title', '')
                if not source or source == 'Unknown':
                    source = extract_domain_name(link)
                
                # 빈 설명 처리
                if not description or description.strip() == '':
                    description = "뉴스 내용은 원문 링크에서 확인하세요"
                
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
                    'title': title[:200] if title else "제목 없음",  # 제목 길이 제한
                    'description': description[:500] if description else "내용 없음",  # 설명 길이 제한
                    'category': source[:100] if source else "Unknown",
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
            news_item['title'],             # B: title
            news_item['description'],       # C: description
            news_item['category'],          # D: category
            news_item['tags'],              # E: tags
            news_item['upload_date'],       # F: upload_date
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
    print("🐌 안전한 속도로 처리합니다 (중복 체크 없음, 3초 대기)")
    
    for rss_url in RSS_FEEDS:
        news_items = fetch_rss_news(rss_url, KEYWORDS, initial_mode)
        total_found += len(news_items)
        all_news_items.extend(news_items)
    
    # 발행일자 기준으로 정렬 (오래된 것부터)
    all_news_items.sort(key=lambda x: x.get('pub_datetime', datetime.now()))
    
    print(f"\n📊 총 {len(all_news_items)}개 뉴스를 시간순으로 추가 중...")
    print("⏰ 각 뉴스마다 3초씩 대기하여 안전하게 처리합니다...")
    
    # 시트에 추가 (중복 체크 없음)
    for i, news_item in enumerate(all_news_items, 1):
        print(f"📝 진행률: {i}/{len(all_news_items)}")
        if add_news_to_sheet(worksheet, news_item):
            total_collected += 1
    
    # 실행 결과
    end_time = time.time()
    execution_time = round(end_time - start_time, 2)
    
    print(f"\n🎉 뉴스 수집 완료!")
    print(f"🎯 수집 모드: {'초기 대량 수집' if initial_mode else '일반 수집'}")
    print(f"📊 총 발견: {total_found}개")
    print(f"✅ 성공 추가: {total_collected}개")
    print(f"⏱️ 실행 시간: {execution_time}초")
    
    if total_collected == 0:
        print("ℹ️ 새로운 뉴스가 없습니다.")
    else:
        print(f"🌟 {total_collected}개의 뉴스가 추가되었습니다!")
        print("💡 중복은 수동으로 정리해주세요.")

if __name__ == "__main__":
    main()
