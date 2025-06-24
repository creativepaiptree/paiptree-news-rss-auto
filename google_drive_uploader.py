#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import time

class GoogleDriveUploader:
    def __init__(self, credentials_dict):
        self.credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        self.service = build('drive', 'v3', credentials=self.credentials)
        self.folder_id = None
    
    def setup_news_images_folder(self, folder_name="Paiptree_News_Images"):
        """뉴스 이미지용 폴더 생성 또는 찾기"""
        try:
            print(f"📁 Google Drive 폴더 설정: {folder_name}")
            
            # 기존 폴더 검색
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                self.folder_id = results['files'][0]['id']
                print(f"✅ 기존 폴더 사용: {folder_name} (ID: {self.folder_id})")
            else:
                # 새 폴더 생성
                print(f"📝 새 폴더 생성 중: {folder_name}")
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                self.folder_id = folder['id']
                print(f"✅ 새 폴더 생성 완료: {folder_name} (ID: {self.folder_id})")
            
            return self.folder_id
            
        except Exception as e:
            print(f"❌ 폴더 설정 실패: {e}")
            return None
    
    def upload_image(self, image_data, filename):
        """이미지를 Google Drive에 업로드하고 공개 링크 생성"""
        try:
            if not self.folder_id:
                print("❌ 폴더 ID가 설정되지 않음")
                return None
            
            print(f"📤 이미지 업로드 시작: {filename}")
            
            # 파일 메타데이터
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }
            
            # 미디어 업로드
            media = MediaIoBaseUpload(
                io.BytesIO(image_data),
                mimetype='image/jpeg',
                resumable=True
            )
            
            # 파일 업로드
            print("🔄 Google Drive에 업로드 중...")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file['id']
            print(f"✅ 파일 업로드 완료: {file_id}")
            
            # 공개 권한 설정
            print("🔓 공개 권한 설정 중...")
            self.service.permissions().create(
                fileId=file_id,
                body={
                    'role': 'reader',
                    'type': 'anyone'
                }
            ).execute()
            
            # 공개 다운로드 링크 생성
            public_url = f"https://drive.google.com/uc?id={file_id}"
            
            print(f"✅ 이미지 업로드 성공: {filename}")
            print(f"🔗 공개 링크: {public_url}")
            
            return public_url
            
        except Exception as e:
            print(f"❌ 이미지 업로드 실패 {filename}: {e}")
            return None
    
    def list_files_in_folder(self):
        """폴더 내 파일 목록 조회"""
        try:
            if not self.folder_id:
                print("❌ 폴더 ID가 설정되지 않음")
                return []
            
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and trashed=false",
                fields="files(id, name, size, createdTime)"
            ).execute()
            
            files = results.get('files', [])
            print(f"📋 폴더 내 파일 수: {len(files)}개")
            
            for file in files:
                print(f"  - {file['name']} ({file.get('size', 'N/A')} bytes)")
            
            return files
            
        except Exception as e:
            print(f"❌ 파일 목록 조회 실패: {e}")
            return [] 