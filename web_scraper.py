#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse
import logging

class ArticleImageScraper:
    def __init__(self, timeout=10, max_retries=3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_first_image(self, article_url):
        """기사에서 첫 번째 의미있는 이미지 추출"""
        try:
            print(f"🔍 이미지 추출 시작: {article_url}")
            
            # 웹페이지 가져오기
            response = self._fetch_with_retry(article_url)
            if not response:
                print(f"❌ 웹페이지 접근 실패: {article_url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 이미지 후보들 찾기
            image_candidates = []
            
            # 1. og:image 메타 태그 (가장 우선)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                if self._is_valid_image_url(image_url):
                    image_candidates.append({
                        'url': image_url,
                        'priority': 1,
                        'type': 'og_image'
                    })
                    print(f"✅ og:image 발견: {image_url}")
            
            # 2. article 내 첫 번째 이미지
            article_images = soup.find_all('img', src=True)
            for img in article_images[:10]:  # 상위 10개만 확인
                src = img.get('src')
                if src and self._is_valid_image_url(src):
                    # 이미지 크기 확인
                    width = img.get('width', 0)
                    height = img.get('height', 0)
                    
                    # 너무 작은 이미지 제외 (100x100 미만)
                    if width and height and int(width) >= 100 and int(height) >= 100:
                        full_url = urljoin(article_url, src)
                        image_candidates.append({
                            'url': full_url,
                            'priority': 2,
                            'type': 'article_image',
                            'width': width,
                            'height': height
                        })
                        print(f"✅ article 이미지 발견: {full_url} ({width}x{height})")
                        break  # 첫 번째 유효한 이미지만 사용
            
            # 3. 기타 이미지 (fallback)
            if not image_candidates:
                for img in soup.find_all('img', src=True):
                    src = img.get('src')
                    if src and self._is_valid_image_url(src):
                        full_url = urljoin(article_url, src)
                        image_candidates.append({
                            'url': full_url,
                            'priority': 3,
                            'type': 'fallback'
                        })
                        print(f"✅ fallback 이미지 발견: {full_url}")
                        break
            
            # 우선순위에 따라 정렬
            image_candidates.sort(key=lambda x: x['priority'])
            
            if image_candidates:
                selected_image = image_candidates[0]
                print(f"🎯 선택된 이미지: {selected_image['url']} (타입: {selected_image['type']})")
                return selected_image['url']
            else:
                print(f"❌ 유효한 이미지를 찾을 수 없음: {article_url}")
                return None
            
        except Exception as e:
            print(f"❌ 이미지 추출 실패 {article_url}: {e}")
            return None
    
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
                    time.sleep(sleep_time)  # 지수 백오프
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