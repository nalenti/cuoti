import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

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
        fields="files(id, name, mimeType, createdTime)"
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

    fh = io.BytesIO()

    # 3. 智能下载/导出：先尝试直接下载，如果遇到 Google Docs 限制则自动切换为 export 导出
    try:
        print("📥 正在尝试直接下载文件...")
        request = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    except HttpError as e:
        if "fileNotDownloadable" in str(e) or "Only files with binary content can be downloaded" in str(e):
            print("🔄 检测到该文件为在线文档格式，自动切换为 Google Docs 导出模式...")
            fh = io.BytesIO()
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        else:
            # 如果是其他错误，直接抛出
            raise e

    # 4. 保存到本地仓库目录（统一使用 utf-8 编码写入）
    file_content = fh.getvalue().decode('utf-8')
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(file_content)
        
    print(f"✅ 成功将 {file_name} 抓取并保存到仓库！")

if __name__ == "__main__":
    main()
