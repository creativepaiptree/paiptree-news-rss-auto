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

# 환경변수에서 설정 읽기
def get_config():
    """환경변수에서 설정 정보 읽기"""
    try:
        # Google Sheets 인증 정보
        google_creds = os.environ.get('GOOGLE_CREDENTIALS')
        if not google_creds:
            raise ValueError("GOOGLE_CREDENTIALS 환경변수가 설정되지 않았습니다.")
        
        # JSON 파싱
        creds_dict = json.loads(google_creds)
        
        # Google Sheets ID
        sheets_id = os.environ.get('GOOGLE_SHEETS_ID')
        if not sheets_id:
            raise ValueError("GOOGLE_SHEETS_ID 환경변수가 설정되지 않았습니다.")
        
        return creds_dict, sheets_id
    except Exception as e:
        print(f"❌ 설정 읽기 실패: {e}")
        sys.exit(1)

# RSS 피드 목록
RSS_FEEDS = [
    "https://feeds.yna.co.kr/economy",           # 연합뉴스 경제
    "https://rss.cnn.com/rss/edition.rss",      # CNN
    "https://feeds.reuters.com/reuters/businessNews",  # Reuters 비즈니스
    "https://techcrunch.com/feed/",             # TechCrunch
]

# 검색 키워드
KEYWORDS = [
    "paiptree", "Paiptree", "파이프트리",
    "farmersmind", "Farmersmind", "파머스마인드", 
    "farmers mind", "Farmers Mind"
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
            worksheet = sheet.add_worksheet(title='news_data', rows=1000, cols=10)
            
            # 헤더 추가
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

def fetch_rss_news(rss_url, keywords):
    """RSS 피드에서 뉴스 가져오기"""
    news_items = []
    
    try:
        print(f"📡 RSS 피드 확인 중: {rss_url}")
        
        # RSS 피드 파싱
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            print(f"⚠️ RSS 피드 파싱 경고: {rss_url}")
        
        # 각 뉴스 아이템 확인
        for entry in feed.entries:
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
                else:
                    pub_date = datetime.now().strftime('%Y-%m-%d')
                
                # 언론사명 추출
                source = feed.feed.get('title', 'Unknown')
                
                # 썸네일 이미지 추출 시도
                thumbnail_url = ""
                if hasattr(entry, 'media_thumbnail'):
                    thumbnail_url = entry.media_thumbnail[0]['url'] if entry.media_thumbnail else ""
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.type.startswith('image/'):
                            thumbnail_url = enc.href
                            break
                
                news_item = {
                    'id': generate_news_id(link),
                    'title': title[:200],  # 제목 길이 제한
                    'description': description[:500],  # 설명 길이 제한
                    'category': source,
                    'tags': ','.join(matched_keywords),
                    'upload_date': pub_date,
                    'download_count': '0',
                    'thumbnail_url': thumbnail_url,
                    'original_url': link
                }
                
                news_items.append(news_item)
                print(f"✅ 키워드 매칭: {title[:50]}... (키워드: {matched_keywords})")
        
        print(f"📊 {rss_url}에서 {len(news_items)}개 뉴스 발견")
        return news_items
        
    except Exception as e:
        print(f"❌ RSS 피드 처리 실패 {rss_url}: {e}")
        return []

def generate_news_id(url):
    """URL 기반으로 고유 ID 생성"""
    return f"news_{hashlib.md5(url.encode()).hexdigest()[:12]}"

def is_duplicate_news(worksheet, news_id, original_url):
    """중복 뉴스 확인"""
    try:
        # 모든 기존 데이터 가져오기
        all_records = worksheet.get_all_records()
        
        for record in all_records:
            # ID 또는 URL이 일치하면 중복
            if record.get('id') == news_id or record.get('original_url') == original_url:
                return True
        
        return False
    except Exception as e:
        print(f"⚠️ 중복 확인 실패: {e}")
        return False

def add_news_to_sheet(worksheet, news_item):
    """Google Sheets에 뉴스 추가"""
    try:
        # 중복 확인
        if is_duplicate_news(worksheet, news_item['id'], news_item['original_url']):
            print(f"⏭️ 중복 뉴스 스킵: {news_item['title'][:50]}...")
            return False
        
        # 시트에 추가
        row_data = [
            news_item['id'],
            news_item['title'],
            news_item['description'],
            news_item['category'],
            news_item['tags'],
            news_item['upload_date'],
            news_item['download_count'],
            news_item['thumbnail_url'],
            news_item['original_url']
        ]
        
        worksheet.append_row(row_data)
        print(f"✅ 뉴스 추가: {news_item['title'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ 뉴스 추가 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 Paiptree 뉴스 수집 시작")
    print(f"📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    # 설정 읽기
    creds_dict, sheets_id = get_config()
    
    # Google Sheets 연결
    worksheet = setup_google_sheets(creds_dict, sheets_id)
    
    # 뉴스 수집
    total_collected = 0
    total_found = 0
    
    print(f"🔍 {len(RSS_FEEDS)}개 RSS 피드에서 뉴스 검색 중...")
    print(f"🏷️ 검색 키워드: {', '.join(KEYWORDS)}")
    
    for rss_url in RSS_FEEDS:
        news_items = fetch_rss_news(rss_url, KEYWORDS)
        total_found += len(news_items)
        
        for news_item in news_items:
            if add_news_to_sheet(worksheet, news_item):
                total_collected += 1
            
            # API 호출 제한 고려하여 잠시 대기
            time.sleep(0.5)
    
    # 실행 결과
    end_time = time.time()
    execution_time = round(end_time - start_time, 2)
    
    print(f"\n🎉 뉴스 수집 완료!")
    print(f"📊 총 발견: {total_found}개")
    print(f"✅ 새로 추가: {total_collected}개")
    print(f"⏱️ 실행 시간: {execution_time}초")
    
    if total_collected == 0:
        print("ℹ️ 새로운 뉴스가 없습니다.")
    else:
        print(f"🌟 {total_collected}개의 새로운 뉴스가 추가되었습니다!")

if __name__ == "__main__":
    main()