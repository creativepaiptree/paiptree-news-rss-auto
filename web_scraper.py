#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import time
import re
import json
from urllib.parse import urljoin, urlparse
import logging
from PIL import Image
from io import BytesIO

class ArticleImageScraper:
    def __init__(self, timeout=10, max_retries=3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_largest_image(self, article_url):
        """🔥 기사에서 가장 큰 이미지 추출 - 실제 크기 측정"""
        try:
            print(f"🔍 이미지 추출 시작: {article_url}")
            
            # 웹페이지 가져오기
            response = self._fetch_with_retry(article_url)
            if not response:
                print(f"❌ 웹페이지 접근 실패: {article_url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 🔥 모든 이미지 후보 수집 (실제 크기 측정용)
            all_image_urls = set()
            
            # 1. og:image 메타 태그
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                if self._is_valid_image_url(image_url) and not self._is_excluded_image(image_url):
                    all_image_urls.add(urljoin(article_url, image_url))
                    print(f"✅ og:image 발견: {image_url}")
            
            # 2. 기사 본문 영역 내 모든 이미지
            article_selectors = [
                'article img', 'main img', '.article-content img',
                '.content img', '.post-content img', '.entry-content img',
                '[data-article] img', '.article-body img', '.news-content img'
            ]
            
            for selector in article_selectors:
                article_images = soup.select(selector)
                for img in article_images:
                    src = img.get('src') or img.get('data-src') or img.get('data-original')
                    if src and self._is_valid_image_url(src) and not self._is_excluded_image(src):
                        full_url = urljoin(article_url, src)
                        all_image_urls.add(full_url)
                        print(f"✅ 본문 이미지 발견: {src}")
            
            # 3. 일반 이미지 (본문에서 충분히 못 찾았을 경우만)
            if len(all_image_urls) < 5:
                general_images = soup.find_all('img', src=True)
                for img in general_images[:10]:  # 최대 10개만 확인
                    src = img.get('src')
                    if src and self._is_valid_image_url(src) and not self._is_excluded_image(src):
                        full_url = urljoin(article_url, src)
                        all_image_urls.add(full_url)
            
            print(f"📊 총 {len(all_image_urls)}개 이미지 후보 발견")
            
            if not all_image_urls:
                print(f"❌ 유효한 이미지를 찾을 수 없음: {article_url}")
                return None
            
            # 🔥 핵심: 모든 이미지의 실제 크기 측정
            image_sizes = []
            for img_url in list(all_image_urls)[:15]:  # 최대 15개만 측정 (성능 고려)
                actual_size = self._get_actual_image_size(img_url)
                if actual_size:
                    width, height = actual_size
                    area = width * height
                    
                    # 최소 크기 필터링 (200x150 이상)
                    if width >= 200 and height >= 150:
                        image_sizes.append({
                            'url': img_url,
                            'width': width,
                            'height': height,
                            'area': area
                        })
                        print(f"📐 이미지 크기: {width}x{height} (면적: {area:,}px²) - {img_url}")
                    else:
                        print(f"❌ 너무 작은 이미지: {width}x{height} - {img_url}")
                else:
                    print(f"⚠️ 크기 측정 실패: {img_url}")
            
            # 면적 기준으로 정렬하여 가장 큰 이미지 선택
            if image_sizes:
                largest_image = max(image_sizes, key=lambda x: x['area'])
                print(f"🏆 가장 큰 이미지 선택: {largest_image['width']}x{largest_image['height']} (면적: {largest_image['area']:,}px²)")
                print(f"🎯 선택된 URL: {largest_image['url']}")
                return largest_image['url']
            else:
                print(f"❌ 유효한 크기의 이미지를 찾을 수 없음: {article_url}")
                return None
            
        except Exception as e:
            print(f"❌ 이미지 추출 실패 {article_url}: {e}")
            return None
    
    def _get_actual_image_size(self, image_url):
        """🔥 실제 이미지 파일을 다운로드해서 크기 측정"""
        try:
            print(f"📏 이미지 크기 측정 중: {image_url[:60]}...")
            
            # 이미지 부분 다운로드 (헤더만 우선 시도)
            response = self.session.get(
                image_url, 
                timeout=self.timeout,
                stream=True,
                headers={'Range': 'bytes=0-2048'}  # 처음 2KB만 다운로드
            )
            
            if response.status_code not in [200, 206]:  # 206은 Partial Content
                print(f"⚠️ HTTP {response.status_code}: {image_url}")
                return None
            
            # Content-Type 확인
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                print(f"⚠️ 이미지가 아님: {content_type}")
                return None
            
            # 이미지 데이터 읽기
            image_data = BytesIO()
            downloaded_size = 0
            max_download = 50 * 1024  # 최대 50KB까지만 다운로드
            
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    image_data.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # PIL로 크기 측정 시도 (부분 데이터로도 가능한 경우가 많음)
                    try:
                        image_data.seek(0)
                        with Image.open(image_data) as img:
                            width, height = img.size
                            print(f"✅ 크기 측정 성공: {width}x{height}")
                            return (width, height)
                    except Exception:
                        pass  # 아직 충분한 데이터가 없음
                    
                    # 최대 다운로드 크기 체크
                    if downloaded_size >= max_download:
                        break
            
            # 마지막 시도
            try:
                image_data.seek(0)
                with Image.open(image_data) as img:
                    width, height = img.size
                    print(f"✅ 크기 측정 성공: {width}x{height}")
                    return (width, height)
            except Exception as e:
                print(f"❌ PIL 이미지 처리 실패: {e}")
                
                # PIL 실패시 전체 이미지 다운로드 시도
                try:
                    full_response = self.session.get(image_url, timeout=self.timeout)
                    if full_response.status_code == 200:
                        with Image.open(BytesIO(full_response.content)) as img:
                            width, height = img.size
                            print(f"✅ 전체 다운로드 후 크기 측정 성공: {width}x{height}")
                            return (width, height)
                except Exception as e2:
                    print(f"❌ 전체 다운로드도 실패: {e2}")
                
                return None
                
        except Exception as e:
            print(f"❌ 이미지 크기 측정 실패 {image_url}: {e}")
            return None
    
    # 기존 함수들 유지 (호환성을 위해)
    def extract_first_image(self, article_url):
        """기존 호환성을 위한 함수 - 새로운 largest_image 함수 호출"""
        return self.extract_largest_image(article_url)
    
    def _fetch_with_retry(self, url):
        """재시도 로직이 포함된 웹페이지 가져오기"""
        for attempt in range(self.max_retries):
            try:
                print(f"📡 웹페이지 가져오기 시도 {attempt + 1}/{self.max_retries}: {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                print(f"✅ 웹페이지 가져오기 성공: {url}")
                return response
            except Exception as e:
                print(f"⚠️ 시도 {attempt + 1} 실패: {e}")
                if attempt < self.max_retries - 1:
                    sleep_time = 2 ** attempt
                    print(f"⏳ {sleep_time}초 대기 후 재시도...")
                    time.sleep(sleep_time)
                else:
                    print(f"💥 모든 재시도 실패: {url}")
                    return None
    
    def _is_valid_image_url(self, url):
        """유효한 이미지 URL인지 확인"""
        if not url:
            return False
        
        # 상대 URL은 유효하다고 가정
        if url.startswith('/'):
            return True
        
        # 절대 URL 검증
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # 이미지 파일 확장자 확인
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in image_extensions):
                return True
            
            # 확장자가 없어도 유효할 수 있음 (동적 이미지)
            return True
            
        except Exception:
            return False
    
    def _is_excluded_image(self, url):
        """제외되어야 할 이미지 URL인지 확인 (로고, 광고 등)"""
        if not url or not isinstance(url, str):
            return True
        
        url_lower = url.lower()
        
        # 로고 및 아이콘 관련 키워드 (더 강화)
        exclude_keywords = [
            'logo', 'icon', 'favicon', 'symbol', 'brand',
            'header', 'footer', 'nav', 'menu', 'sidebar',
            'banner', 'ad', 'advertisement', 'sponsor',
            'social', 'share', 'facebook', 'twitter', 'instagram',
            'avatar', 'profile', 'author', 'writer', 'reporter',
            'button', 'arrow', 'loading', 'spinner',
            'placeholder', 'default', 'blank', 'thumb',
            'thumbnail_default', 'no-image', 'noimage',
            'google', 'youtube', 'naver', 'kakao', 'daum',
            '1x1', 'pixel', 'tracking', 'analytics',
            'print', 'email', 'bookmark', 'subscribe'
        ]
        
        # URL에 제외 키워드 포함 여부 확인
        for keyword in exclude_keywords:
            if keyword in url_lower:
                return True
        
        # 매우 작은 이미지 제외 (URL에 크기 정보 있을 경우)
        size_patterns = [
            r'\b\d{1,2}x\d{1,2}\b',  # 50x50 같은 작은 사이즈
            r'\b[1-9]\dx[1-9]\d\b'   # 10x10 ~ 99x99
        ]
        
        for pattern in size_patterns:
            if re.search(pattern, url):
                match = re.search(r'\b(\d+)x(\d+)\b', url)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                    if width < 200 or height < 150:
                        return True
        
        return False