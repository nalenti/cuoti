import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

sa_key_info = json.loads(os.environ["GCP_SA_KEY"])
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TARGET_DIR = "study"

def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    credentials = service_account.Credentials.from_service_account_info(
        sa_key_info, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)

    # 放大检索范围：去掉 'root' 限制，直接查全盘所有文件，看看机器人到底能扫到啥
    query = "trashed = false"

    results = service.files().list(
        q=query, 
        pageSize=50, 
        orderBy="createdTime desc",
        fields="files(id, name, mimeType)"
    ).execute()
    files = results.get('files', [])

    print(f"🤖 机器人视野内一共发现了 {len(files)} 个文件/文件夹：")
    for f in files:
        print(f" - [名称: {f['name']}] (类型: {f['mimeType']})")

    if not files:
        print("📭 机器人什么也没扫到，说明权限没配对或者凭证无效！")
        return

    for file in files:
        file_id = file['id']
        file_name = file['name']
        mime_type = file['mimeType']
        
        if mime_type == 'application/vnd.google-apps.folder' or '.md' not in file_name:
            continue

        print(f"📥 正在同步错题文件: {file_name}")
        fh = io.BytesIO()
        try:
            if mime_type == 'application/vnd.google-apps.document':
                request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            else:
                request = service.files().get_media(fileId=file_id)

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        except Exception as e:
            print(f"❌ 失败: {e}")
            continue

        file_path = os.path.join(TARGET_DIR, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fh.getvalue().decode('utf-8', errors='ignore'))
        print(f"✅ 成功写入 {file_path}")

if __name__ == "__main__":
    main()
