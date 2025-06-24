#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import time
import re
import json
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
        """기사에서 첫 번째 의미있는 이미지 추출 - 스마트 로직 강화"""
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
                if self._is_valid_image_url(image_url) and not self._is_excluded_image(image_url):
                    image_candidates.append({
                        'url': image_url,
                        'priority': 1,
                        'type': 'og_image',
                        'score': 100
                    })
                    print(f"✅ og:image 발견: {image_url}")
            
            # 2. 구조화 데이터 이미지 (JSON-LD)
            json_ld_images = self._extract_structured_data_images(soup)
            for img_url in json_ld_images:
                if self._is_valid_image_url(img_url) and not self._is_excluded_image(img_url):
                    image_candidates.append({
                        'url': img_url,
                        'priority': 2,
                        'type': 'structured_data',
                        'score': 90
                    })
                    print(f"✅ 구조화 데이터 이미지 발견: {img_url}")
            
            # 3. 기사 본문 영역 내 이미지 (CSS 선택자 우선순위)
            article_selectors = [
                'article img',
                'main img', 
                '.article-content img',
                '.content img',
                '.post-content img',
                '.entry-content img',
                '[data-article] img',
                '.article-body img'
            ]
            
            for selector in article_selectors:
                article_images = soup.select(selector)
                for img in article_images[:5]:  # 각 선택자당 상위 5개만
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_image_url(src) and not self._is_excluded_image(src):
                        # 이미지 품질 점수 계산
                        score = self._calculate_image_score(img, selector)
                        if score >= 50:  # 최소 점수 이상만 선택
                            full_url = urljoin(article_url, src)
                            image_candidates.append({
                                'url': full_url,
                                'priority': 3,
                                'type': f'article_{selector.split()[0]}',
                                'score': score,
                                'width': img.get('width'),
                                'height': img.get('height'),
                                'alt': img.get('alt', '')
                            })
                            print(f"✅ {selector} 이미지 발견: {full_url} (점수: {score})")
                break  # 첫 번째 성공한 선택자에서만 가져오기
            
            # 4. 일반 이미지 중 큰 것들 (더 엄격한 기준)
            if len(image_candidates) < 3:  # 후보가 부족할 때만
                general_images = soup.find_all('img', src=True)
                for img in general_images:
                    src = img.get('src')
                    if src and self._is_valid_image_url(src) and not self._is_excluded_image(src):
                        score = self._calculate_image_score(img, 'general')
                        if score >= 30:  # 일반 이미지는 더 낮은 기준
                            full_url = urljoin(article_url, src)
                            image_candidates.append({
                                'url': full_url,
                                'priority': 4,
                                'type': 'general',
                                'score': score
                            })
                            print(f"✅ 일반 이미지 발견: {full_url} (점수: {score})")
                            if len(image_candidates) >= 10:  # 너무 많이 수집하지 않음
                                break
            
            # 점수와 우선순위에 따라 정렬
            image_candidates.sort(key=lambda x: (-x['priority'], -x['score']))
            
            if image_candidates:
                selected_image = image_candidates[0]
                print(f"🎯 선택된 이미지: {selected_image['url']} (타입: {selected_image['type']}, 점수: {selected_image['score']})")
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
    
    def _is_excluded_image(self, url):
        """제외되어야 할 이미지 URL인지 확인 (로고, 광고 등)"""
        if not url or not isinstance(url, str):
            return True
        
        url_lower = url.lower()
        
        # 로고 및 아이콘 관련 키워드
        exclude_keywords = [
            'logo', 'icon', 'favicon', 'symbol', 'brand',
            'header', 'footer', 'nav', 'menu', 'sidebar',
            'banner', 'ad', 'advertisement', 'sponsor',
            'social', 'share', 'facebook', 'twitter', 'instagram',
            'avatar', 'profile', 'author', 'writer',
            'button', 'arrow', 'loading', 'spinner',
            'placeholder', 'default', 'blank',
            'thumbnail_default', 'no-image', 'noimage',
            'google', 'youtube', 'naver', 'kakao',  # 플랫폼 로고
            '1x1', 'pixel', 'tracking',  # 추적 이미지
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
                # 사이즈 추출해서 너무 작으면 제외
                match = re.search(r'\b(\d+)x(\d+)\b', url)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                    if width < 200 or height < 150:  # 200x150 미만 제외
                        return True
        
        return False
    
    def _extract_structured_data_images(self, soup):
        """구조화 데이터(JSON-LD)에서 이미지 추출"""
        images = []
        
        try:
            # JSON-LD 스크립트 찾기
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # 여러 형태의 데이터 처리
                    if isinstance(data, list):
                        for item in data:
                            images.extend(self._extract_images_from_json_ld(item))
                    else:
                        images.extend(self._extract_images_from_json_ld(data))
                        
                except (json.JSONDecodeError, TypeError):
                    continue
                    
        except Exception as e:
            print(f"⚠️ JSON-LD 처리 오류: {e}")
            
        return images[:3]  # 최대 3개만 반환
    
    def _extract_images_from_json_ld(self, data):
        """개별 JSON-LD 데이터에서 이미지 추출"""
        images = []
        
        if not isinstance(data, dict):
            return images
        
        # 다양한 이미지 필드 찾기
        image_fields = ['image', 'thumbnailUrl', 'contentUrl', 'url']
        
        for field in image_fields:
            if field in data:
                image_data = data[field]
                
                if isinstance(image_data, str):
                    images.append(image_data)
                elif isinstance(image_data, list):
                    for img in image_data:
                        if isinstance(img, str):
                            images.append(img)
                        elif isinstance(img, dict) and 'url' in img:
                            images.append(img['url'])
                elif isinstance(image_data, dict) and 'url' in image_data:
                    images.append(image_data['url'])
        
        return images
    
    def _calculate_image_score(self, img_element, selector_type):
        """이미지 품질 점수 계산 (0-100)"""
        score = 0
        
        # 1. 기본 점수 (선택자 타입에 따라)
        base_scores = {
            'article': 60,
            'main': 50, 
            '.article-content': 55,
            '.content': 45,
            '.post-content': 50,
            '.entry-content': 50,
            'general': 20
        }
        
        for key, base_score in base_scores.items():
            if key in selector_type:
                score += base_score
                break
        else:
            score += 20  # 기본 점수
        
        # 2. 이미지 크기 점수
        try:
            width = int(img_element.get('width', 0) or 0)
            height = int(img_element.get('height', 0) or 0)
            
            if width >= 600 and height >= 400:  # 큰 이미지
                score += 30
            elif width >= 400 and height >= 300:  # 중간 이미진
                score += 20
            elif width >= 300 and height >= 200:  # 작은 이미진
                score += 10
            elif width > 0 and height > 0 and (width < 150 or height < 100):  # 너무 작음
                score -= 20
                
        except (ValueError, TypeError):
            pass
        
        # 3. alt 텍스트 점수 (의미있는 설명)
        alt_text = img_element.get('alt', '').lower()
        if alt_text:
            if len(alt_text) > 10:  # 상세한 alt 텍스트
                score += 15
            elif len(alt_text) > 3:  # 기본 alt 텍스트
                score += 10
            
            # alt 텍스트에 로고/아이콘 키워드 있으면 감점
            exclude_words = ['logo', 'icon', 'avatar', 'profile', 'button', 'banner']
            if any(word in alt_text for word in exclude_words):
                score -= 25
        
        # 4. CSS 클래스 점수
        class_names = ' '.join(img_element.get('class', [])).lower()
        if class_names:
            # 긴정적 클래스
            positive_classes = ['article', 'content', 'main', 'featured', 'hero', 'primary']
            for cls in positive_classes:
                if cls in class_names:
                    score += 5
                    break
            
            # 부정적 클래스
            negative_classes = ['logo', 'icon', 'avatar', 'button', 'banner', 'ad', 'sidebar']
            for cls in negative_classes:
                if cls in class_names:
                    score -= 20
                    break
        
        # 5. data-src 사용 (지연 로딩) - 약간 감점
        if img_element.get('data-src') and not img_element.get('src'):
            score -= 5
        
        return max(0, min(100, score))  # 0-100 범위로 제한 