#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from PIL import Image
import io
import os
import hashlib
import time
from urllib.parse import urlparse

class ImageProcessor:
    def __init__(self, max_size=(400, 300), quality=85):
        self.max_size = max_size
        self.quality = quality
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def download_and_optimize(self, image_url, filename=None):
        """이미지 다운로드 및 최적화"""
        try:
            print(f"📥 이미지 다운로드 시작: {image_url}")
            
            # 이미지 다운로드
            response = self.session.get(image_url, timeout=15)
            response.raise_for_status()
            
            print(f"✅ 이미지 다운로드 완료: {len(response.content)} bytes")
            
            # 이미지 처리
            image = Image.open(io.BytesIO(response.content))
            original_size = image.size
            original_mode = image.mode
            
            print(f"📊 원본 이미지: {original_size} ({original_mode})")
            
            # RGBA를 RGB로 변환 (JPEG는 알파 채널 지원 안함)
            if image.mode in ('RGBA', 'LA', 'P'):
                print(f"🔄 이미지 모드 변환: {image.mode} → RGB")
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # 크기 조정 (비율 유지)
            image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            new_size = image.size
            print(f"📏 크기 조정: {original_size} → {new_size}")
            
            # 파일명 생성
            if not filename:
                filename = self._generate_filename(image_url, new_size)
            
            print(f"📝 파일명: {filename}")
            
            # 최적화된 이미지 저장
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='JPEG', quality=self.quality, optimize=True)
            output_buffer.seek(0)
            
            file_size = len(output_buffer.getvalue())
            print(f"💾 최적화 완료: {file_size} bytes (품질: {self.quality}%)")
            
            return {
                'data': output_buffer.getvalue(),
                'filename': filename,
                'size': new_size,
                'format': 'JPEG',
                'file_size': file_size,
                'original_size': original_size
            }
            
        except Exception as e:
            print(f"❌ 이미지 처리 실패 {image_url}: {e}")
            return None
    
    def _generate_filename(self, original_url, image_size):
        """고유한 파일명 생성"""
        # URL에서 도메인 추출
        domain = urlparse(original_url).netloc.replace('.', '_')
        if not domain:
            domain = 'unknown'
        
        # 이미지 크기 정보
        size_str = f"{image_size[0]}x{image_size[1]}"
        
        # 해시 생성 (URL 기반)
        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
        
        # 타임스탬프
        timestamp = int(time.time())
        
        return f"news_thumb_{domain}_{size_str}_{url_hash}_{timestamp}.jpg" 