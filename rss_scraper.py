#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import feedparser
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# RSS 피드 목록 - 네이버 + 구글 뉴스
RSS_FEEDS = [
    "http://newssearch.naver.com/search.naver?where=rss&query=파이프트리",
    "http://newssearch.naver.com/search.naver?where=rss&query=파머스마인드",
    "http://newssearch.naver.com/search.naver?where=rss&query=paiptree",
    "http://newssearch.naver.com/search.naver?where=rss&query=farmersmind",
    "https://news.google.com/rss/search?q=파이프트리&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=파머스마인드&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=paiptree&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=farmersmind&hl=ko&gl=KR&ceid=KR:ko",
]

KEYWORDS = ["파이프트리", "파머스마인드", "paiptree", "farmersmind"]


def get_runtime_config():
    initial_mode = os.environ.get("INITIAL_COLLECTION", "false").lower() == "true"
    content_tab = os.environ.get("CONTENT_TAB", "news").lower()
    content_tab = "social" if content_tab == "social" else "news"

    output_json = os.environ.get("OUTPUT_JSON_PATH", "dist/news_payload.json")
    output_csv = os.environ.get("OUTPUT_CSV_PATH", "news_data.csv")

    return {
        "initial_mode": initial_mode,
        "content_tab": content_tab,
        "output_json": output_json,
        "output_csv": output_csv,
    }


def normalize_url(url):
    value = (url or "").strip()
    if not value:
        return ""

    try:
        parsed = urlparse(value)
        filtered_query = [
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=False)
            if key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
            and not key.lower().startswith("utm_")
        ]
        cleaned = parsed._replace(query=urlencode(filtered_query, doseq=True), fragment="")
        return urlunparse(cleaned)
    except Exception:
        return value


def clean_news_description(description, source_name):
    if not description:
        return ""

    cleaned = re.sub(r"<[^>]+>", "", description)
    cleaned = html.unescape(cleaned)

    source_clean = re.escape(source_name) if source_name else ""
    if source_clean:
        cleaned = re.sub(rf"\s*-\s*{source_clean}\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"\s*\({source_clean}\)\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"\s*{source_clean}\s*$", "", cleaned, flags=re.IGNORECASE)

    providers = [
        "연합뉴스", "뉴스1", "뉴시스", "YTN", "SBS", "MBC", "KBS",
        "조선일보", "동아일보", "중앙일보", "한겨레", "경향신문",
    ]
    for provider in providers:
        escaped = re.escape(provider)
        cleaned = re.sub(rf"\s*-\s*{escaped}\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"\s*\({escaped}\)\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"\s*{escaped}\s*$", "", cleaned, flags=re.IGNORECASE)

    patterns = [
        r"\s*\[.*?\]\s*$",
        r"\s*=.*?=\s*$",
        r"\s*\(.*?기자\)\s*$",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_entry_datetime(entry):
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        try:
            return datetime(*published[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def to_iso8601(dt_obj):
    return dt_obj.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_source_name(feed, entry, link):
    source = ""
    entry_source = entry.get("source")
    if isinstance(entry_source, dict):
        source = (entry_source.get("title") or "").strip()

    if not source:
        feed_title = ""
        if hasattr(feed, "feed"):
            feed_title = (getattr(feed.feed, "title", "") or "").strip()
        source = feed_title

    if not source:
        try:
            hostname = urlparse(link).hostname or ""
            source = hostname.replace("www.", "")
        except Exception:
            source = "Unknown"

    return source or "Unknown"


def matched_keywords(title, description, keywords):
    content = f"{title} {description}".lower()
    found = [kw for kw in keywords if kw.lower() in content]
    # 중복 제거 + 순서 유지
    return list(dict.fromkeys(found))


def fetch_rss_news(rss_url, keywords, initial_mode, content_tab):
    news_items = []

    try:
        print(f"📡 RSS 피드 확인 중: {rss_url}")
        feed = feedparser.parse(rss_url)

        if getattr(feed, "bozo", False):
            print(f"⚠️ RSS 파싱 경고: {rss_url}")

        entries = list(getattr(feed, "entries", []))
        print(f"📊 총 {len(entries)}개 엔트리 발견")

        if not initial_mode:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            filtered = []
            for entry in entries:
                published_at = parse_entry_datetime(entry)
                if published_at >= cutoff:
                    filtered.append(entry)
            entries = filtered
            print(f"🗓️ 최근 7일 기준 {len(entries)}개 처리")
        else:
            print(f"🎯 초기 수집 모드: {len(entries)}개 처리")

        for entry in entries:
            title = (entry.get("title") or "").strip()
            raw_description = (entry.get("description") or entry.get("summary") or "").strip()
            link = normalize_url(entry.get("link") or "")

            if not title or not link:
                continue

            tags = matched_keywords(title, raw_description, keywords)
            if not tags:
                continue

            published_dt = parse_entry_datetime(entry)
            source = extract_source_name(feed, entry, link)
            description = clean_news_description(raw_description, source)

            news_items.append(
                {
                    "title": title[:200],
                    "description": description[:500],
                    "category": source[:100],
                    "tags": ",".join(tags),
                    "date": to_iso8601(published_dt),
                    "download_count": 0,
                    "original_url": link,
                    "tab": content_tab,
                    "_pub_dt": published_dt,
                }
            )

        print(f"✅ 매칭 뉴스 {len(news_items)}개")
        return news_items

    except Exception as error:
        print(f"❌ RSS 처리 실패 ({rss_url}): {error}")
        return []


def dedupe_news(news_items):
    unique = {}
    for item in news_items:
        key = item["original_url"]
        existing = unique.get(key)
        if not existing:
            unique[key] = item
            continue

        # 같은 URL이면 더 긴 description을 가진 쪽 선택
        if len(item.get("description", "")) > len(existing.get("description", "")):
            unique[key] = item

    return list(unique.values())


def attach_stable_ids(news_items, content_tab):
    for item in news_items:
        digest = hashlib.sha1(f"{content_tab}:{item['original_url']}".encode("utf-8")).hexdigest()[:24]
        item["id"] = f"{content_tab}_{digest}"


def write_json_payload(news_items, output_path, content_tab):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    rows = [
        {
            "id": item["id"],
            "tab": item["tab"],
            "title": item["title"],
            "description": item["description"],
            "category": item["category"],
            "tags": item["tags"],
            "date": item["date"],
            "download_count": item["download_count"],
            "original_url": item["original_url"],
        }
        for item in news_items
    ]

    payload = {"tab": content_tab, "rows": rows}
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    print(f"✅ JSON 저장 완료: {output_path} ({len(rows)}건)")


def write_csv_export(news_items, output_path):
    headers = ["id", "title", "description", "category", "tags", "date", "download_count", "original_url", "tab"]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for item in news_items:
            writer.writerow(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "description": item["description"],
                    "category": item["category"],
                    "tags": item["tags"],
                    "date": item["date"],
                    "download_count": item["download_count"],
                    "original_url": item["original_url"],
                    "tab": item["tab"],
                }
            )
    print(f"✅ CSV 저장 완료: {output_path} ({len(news_items)}건)")


def main():
    config = get_runtime_config()
    initial_mode = config["initial_mode"]
    content_tab = config["content_tab"]
    output_json = config["output_json"]
    output_csv = config["output_csv"]

    print("🚀 Paiptree 뉴스 수집 시작")
    print(f"📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 수집 모드: {'초기 대량 수집' if initial_mode else '일반 수집(최근 7일)'}")
    print(f"🗂️ 콘텐츠 탭: {content_tab}")

    started_at = time.time()
    all_news = []

    print(f"🔍 RSS 피드 {len(RSS_FEEDS)}개 수집 시작")
    print(f"🏷️ 키워드: {', '.join(KEYWORDS)}")

    for rss_url in RSS_FEEDS:
        items = fetch_rss_news(rss_url, KEYWORDS, initial_mode, content_tab)
        all_news.extend(items)
        time.sleep(0.2)

    found_count = len(all_news)
    deduped = dedupe_news(all_news)
    deduped_count = len(deduped)

    # 오래된 뉴스 -> 최신 뉴스 순으로 정렬
    deduped.sort(key=lambda item: item.get("_pub_dt", datetime.now(timezone.utc)))

    attach_stable_ids(deduped, content_tab)

    # 내부용 키 제거
    for item in deduped:
        item.pop("_pub_dt", None)

    write_json_payload(deduped, output_json, content_tab)
    write_csv_export(deduped, output_csv)

    elapsed = round(time.time() - started_at, 2)

    print("\n🎉 뉴스 수집 완료")
    print(f"📊 총 발견: {found_count}개")
    print(f"🧹 중복 제거 후: {deduped_count}개")
    print(f"✅ 결과 JSON: {output_json}")
    print(f"✅ 결과 CSV: {output_csv}")
    print(f"⏱️ 실행 시간: {elapsed}초")

    if deduped_count == 0:
        print("ℹ️ 신규 데이터가 없습니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"❌ 실행 실패: {error}")
        sys.exit(1)
