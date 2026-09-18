import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 从环境变量中读取刚才存入的 JSON 密钥
sa_key_info = json.loads(os.environ["GCP_SA_KEY"])
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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

    # 3. 获取根目录下（'root' in parents）的所有未删除文件和文件夹
    query = "trashed = false and 'root' in parents"

    results = service.files().list(
        q=query, 
        pageSize=50, 
        orderBy="createdTime desc",
        fields="files(id, name, mimeType, createdTime)"
    ).execute()
    files = results.get('files', [])

    if not files:
        print("📭 谷歌网盘根目录下未找到任何文件")
        return

    print(f"📄 共发现 {len(files)} 个云端根目录项目，开始按规则筛选错题...")

    # 4. 循环遍历根目录下的项目
    for file in files:
        file_id = file['id']
        file_name = file['name']
        mime_type = file['mimeType']
        
        # 🎯 双重过滤：
        # ① 如果是文件夹（例如“河西走廊”），直接跳过，绝不拉取！
        if mime_type == 'application/vnd.google-apps.folder':
            print(f"⏭️ 跳过文件夹: {file_name}")
            continue

        # ② 如果文件名中不包含 ".md"，直接跳过
        if '.md' not in file_name:
            print(f"⏭️ 跳过无关文件: {file_name}")
            continue

        print(f"----------------------------------------")
        print(f"📥 正在同步错题文件: {file_name}")

        fh = io.BytesIO()

        # 5. 智能导出/下载
        try:
            if mime_type == 'application/vnd.google-apps.document':
                # Google 在线文档导出为纯文本
                request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            else:
                # 普通文件直接下载
                request = service.files().get_media(fileId=file_id)

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        except Exception as e:
            print(f"❌ 处理文件 {file_name} 失败: {e}")
            continue

        # 6. 保存到本地的 study/ 目录中
        file_path = os.path.join(TARGET_DIR, file_name)
        try:
            file_content = fh.getvalue().decode('utf-8')
        except UnicodeDecodeError:
            file_content = fh.getvalue().decode('gbk', errors='ignore')

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
            
        print(f"✅ [{file_name}] 成功同步并存入 {file_path}！")

    print(f"----------------------------------------")
    print("🎉 错题同步完成！")

if __name__ == "__main__":
    main()
