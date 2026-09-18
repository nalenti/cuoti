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

# 🎯 改动 1：将 FOLDER_ID 设为空（表示直接扫描根目录，或者不再按子文件夹 ID 过滤）
FOLDER_ID = '' 

# 📂 GitHub 仓库中存放错题的目标文件夹名称（已设置为 study）
TARGET_DIR = "study"

def main():
    # 1. 确保本地目标文件夹存在，如果不存在则自动创建
    os.makedirs(TARGET_DIR, exist_ok=True)

    # 2. 授权登录 Google Drive
    credentials = service_account.Credentials.from_service_account_info(
        sa_key_info, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)

    # 3. 🎯 改动 2：构建查询条件：查找根目录下（'root' in parents）、名字包含 .md 且未被删除的文件
    query = "name contains '.md' and trashed = false and 'root' in parents"

    results = service.files().list(
        q=query, 
        pageSize=50, 
        orderBy="createdTime desc",
        fields="files(id, name, mimeType, createdTime)"
    ).execute()
    files = results.get('files', [])

    if not files:
        print("📭 谷歌网盘根目录下未找到任何 .md 文件")
        return

    print(f"📄 共发现 {len(files)} 个云端 Markdown 文件，开始同步到仓库的 '{TARGET_DIR}' 目录下...")

    # 4. 循环遍历每一个找到 .md 的文件并依次下载/导出
    for file in files:
        file_id = file['id']
        file_name = file['name']
        print(f"----------------------------------------")
        print(f"📥 正在处理文件: {file_name}")

        fh = io.BytesIO()

        # 智能容错：直接下载，如果遇到 Google Docs 在线文档限制则自动切换为 export 导出
        try:
            request = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        except HttpError as e:
            if "fileNotDownloadable" in str(e) or "Only files with binary content can be downloaded" in str(e):
                print(f"🔄 [{file_name}] 为在线文档格式，切换为导出模式...")
                fh = io.BytesIO()
                request = service.files().export_media(fileId=file_id, mimeType='text/plain')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            else:
                raise e

        # 5. 组合路径并保存到指定的子文件夹中
        file_path = os.path.join(TARGET_DIR, file_name)
        file_content = fh.getvalue().decode('utf-8')
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
            
        print(f"✅ [{file_name}] 成功同步并存入 {file_path}！")

    print(f"----------------------------------------")
    print("🎉 所有文件同步完成！")

if __name__ == "__main__":
    main()
