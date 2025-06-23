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
        # Google Sheets 인증 정보 (파일에서 읽음으로 변경됨)
        with open('credentials.json') as f:
            creds_dict = json.load(f)

        # Google Sheets ID
        sheets_id = os.environ.get('GOOGLE_SHEETS_ID')
        if not sheets_id:
            raise ValueError("GOOGLE_SHEETS_ID 환경변수가 설정되지 않았습니다.")

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

# 검색 키워드
KEYWORDS = ["파이프트리", "파머스마인드", "paiptree", "farmersmind"]

def setup_google_sheets(creds_dict, sheets_id):
    try:
        print("🔗 Google Sheets 연결 중...")
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(sheets_id)
        try:
            worksheet = sheet.worksheet('news_data')
            print("✅ 기존 news_data 시트 발견")
        except gspread.WorksheetNotFound:
            print("📝 news_data 시트 생성 중...")
            worksheet = sheet.add_worksheet(title='news_data', rows=1000, cols=21)
            headers = [
                'id', 'title', 'description', 'category', 'tags',
                'upload_date', 'file_size', 'file_format', 'dimensions',
                'creator', 'brand_alignment', 'usage_rights', 'version',
                'download_count', 'rating', 'thumbnail_url', 'file_url',
                'original_url', 'status', 'featured', 'created_at'
            ]
            worksheet.append_row(headers)
            print("✅ news_data 시트 생성 완료")
        return worksheet
    except Exception as e:
        print(f"❌ Google Sheets 연결 실패: {e}")
        sys.exit(1)

def fetch_rss_news(rss_url, keywords):
    news_items = []
    try:
        print(f"📡 RSS 피드 확인 중: {rss_url}")
        feed = feedparser.parse(rss_url)
        if feed.bozo:
            print(f"⚠️ RSS 피드 파싱 경고: {rss_url}")
        for entry in feed.entries:
            title = entry.get('title', '')
            description = entry.get('description', '') or entry.get('summary', '')
            link = entry.get('link', '')
            content_to_check = f"{title} {description}".lower()
            matched_keywords = [kw for kw in keywords if kw.lower() in content_to_check]
            if matched_keywords:
                published = entry.get('published_parsed')
                pub_date = datetime(*published[:6]).strftime('%Y-%m-%d') if published else datetime.now().strftime('%Y-%m-%d')
                source = feed.feed.get('title', 'Unknown')
                thumbnail_url = ""
                if hasattr(entry, 'media_thumbnail'):
                    thumbnail_url = entry.media_thumbnail[0]['url'] if entry.media_thumbnail else ""
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.type.startswith('image/'):
                            thumbnail_url = enc.href
                            break
                news_item = {
                    'title': title[:200],
                    'description': description[:500],
                    'category': source,
                    'tags': ','.join(matched_keywords),
                    'upload_date': pub_date,
                    'download_count': 0,
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

def generate_sequential_id(worksheet):
    try:
        all_records = worksheet.get_all_records()
        if not all_records:
            return "001"
        max_num = 0
        for record in all_records:
            try:
                current_id = str(record.get('id', '0'))
                num = int(current_id.lstrip('0')) if current_id.strip() else 0
                max_num = max(max_num, num)
            except (ValueError, TypeError):
                continue
        return f"{max_num + 1:03d}"
    except Exception as e:
        print(f"⚠️ ID 생성 실패, 임시 ID 사용: {e}")
        return f"{int(time.time() % 10000):04d}"

def is_duplicate_news(worksheet, original_url):
    try:
        all_records = worksheet.get_all_records()
        return any(record.get('original_url') == original_url for record in all_records)
    except Exception as e:
        print(f"⚠️ 중복 확인 실패: {e}")
        return False

def add_news_to_sheet(worksheet, news_item):
    try:
        if is_duplicate_news(worksheet, news_item['original_url']):
            print(f"⏭️ 중복 뉴스 스킵: {news_item['title'][:50]}...")
            return False
        news_id = generate_sequential_id(worksheet)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row_data = [
            news_id, news_item['title'], news_item['description'], news_item['category'], news_item['tags'],
            news_item['upload_date'], 'N/A', 'news', 'N/A', news_item['category'],
            'high', 'read-only', '1.0', news_item['download_count'], '0',
            news_item['thumbnail_url'], news_item['original_url'], news_item['original_url'], 'active', 'false', current_time
        ]
        worksheet.append_row(row_data)
        print(f"✅ 뉴스 추가 (ID: {news_id}): {news_item['title'][:50]}...")
        return True
    except Exception as e:
        print(f"❌ 뉴스 추가 실패: {e}")
        return False

def main():
    print("🚀 Paiptree 뉴스 수집 시작")
    print(f"📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()
    creds_dict, sheets_id = get_config()
    worksheet = setup_google_sheets(creds_dict, sheets_id)
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
            time.sleep(0.5)
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
