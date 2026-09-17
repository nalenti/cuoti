import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 从环境变量中读取刚才存入的 JSON 密钥
sa_key_info = json.loads(os.environ["GCP_SA_KEY"])
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def main():
    # 1. 授权登录 Google Drive
    credentials = service_account.Credentials.from_service_account_info(
        sa_key_info, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)

    # 2. 搜索云盘中最新的 .md 文件
    query = "name contains '.md' and trashed = false"
    results = service.files().list(
        q=query, 
        pageSize=5, 
        orderBy="createdTime desc",
        fields="files(id, name, createdTime)"
    ).execute()
    files = results.get('files', [])

    if not files:
        print("📭 谷歌网盘中未找到任何 .md 文件")
        return

    # 获取最新的一份文件
    latest_file = files[0]
    file_id = latest_file['id']
    file_name = latest_file['name']
    print(f"📄 发现最新云端文件: {file_name}")

    # 3. 下载文件内容
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    # 4. 保存到本地仓库目录
    with open(file_name, "wb") as f:
        f.write(fh.getvalue())
    print(f"✅ 成功将 {file_name} 下载到仓库！")

if __name__ == "__main__":
    main()
