import os
import re
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
TARGET_DIR = "study"

def get_notion_existing_titles(headers):
    """查询 Notion 数据库中已存在的页面标题（这里用 '文件名 - 错题标题' 作为唯一标识，防止重复）"""
    existing_titles = set()
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {}

    while True:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"❌ 查询 Notion 数据库失败: {response.text}")
            break
        
        data = response.json()
        results = data.get("results", [])
        
        for page in results:
            properties = page.get("properties", {})
            title_prop = properties.get("标题", {}) or properties.get("Name", {})
            title_list = title_prop.get("title", [])
            if title_list:
                existing_titles.add(title_list[0].get("text", {}).get("content", ""))
                
        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break
            
    return existing_titles

def parse_multiple_questions(file_path):
    """解析文件：提取顶部全局属性，并把正文按“错题 X”切分成多个独立的错题"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def extract_field(pattern, text):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    # 1. 提取顶部全局属性
    base_data = {
        "Child": extract_field(r"Child:\s*(.*)", content),
        "Subject": extract_field(r"Subject:\s*(.*)", content),
        "ReviewDate": extract_field(r"ReviewDate:\s*(.*)", content),
        "Reason": extract_field(r"Reason:\s*(.*)", content),
        "Knowledge": extract_field(r"Knowledge:\s*(.*)", content),
        "ErrorCause": extract_field(r"ErrorCause:\s*(.*)", content),
        "Pitfall": extract_field(r"Pitfall:\s*(.*)", content),
        "Analysis": extract_field(r"Analysis:\s*(.*)", content),
    }

    # 2. 按“错题 X：”把正文切分为多个独立错题
    raw_filename = os.path.splitext(os.path.basename(file_path))[0]
    
    # 按照 “错题 \d+” 进行分割
    parts = re.split(r'(?=错题\s*\d+[:：])', content)
    questions = []

    for part in parts:
        part = part.strip()
        if not part or not re.match(r'^错题\s*\d+[:：]', part):
            continue
        
        # 提取当前错题的标题
        first_line = part.split('\n')[0].strip()
        unique_title = f"{raw_filename} | {first_line}"

        questions.append({
            "title": unique_title,
            "data": base_data,
            "content": part
        })

    return questions

def sync_to_notion():
    if not NOTION_TOKEN or not DATABASE_ID:
        print("❌ 错误: 未设置 NOTION_TOKEN 或 DATABASE_ID 环境变量。")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    print("🔍 正在获取 Notion 数据库中已有的记录清单...")
    existing_titles = get_notion_existing_titles(headers)
    print(f"📊 Notion 中当前已存在 {len(existing_titles)} 条记录。")

    if not os.path.exists(TARGET_DIR):
        print(f"❌ 目录 {TARGET_DIR} 不存在。")
        return

    md_files = [f for f in os.listdir(TARGET_DIR) if f.endswith(".md")]
    print(f"📁 本地 {TARGET_DIR}/ 目录下共发现 {len(md_files)} 个 Markdown 文件。")

    success_count = 0

    for filename in md_files:
        file_path = os.path.join(TARGET_DIR, filename)
        question_list = parse_multiple_questions(file_path)

        print(f"📄 文件 [{filename}] 中共解析出 {len(question_list)} 个独立错题。")

        for q in question_list:
            title = q["title"]
            if title in existing_titles:
                print(f"⏩ 跳过已存在: {title}")
                continue

            data = q["data"]
            print(f"✨ 正在写入 Notion: {title}...")

            payload = {
                "parent": {"database_id": DATABASE_ID},
                "properties": {
                    "标题": {
                        "title": [{"text": {"content": title[:200]}}]
                    },
                    "Child": {
                        "select": {"name": data["Child"]} if data["Child"] else None
                    },
                    "Subject": {
                        "select": {"name": data["Subject"]} if data["Subject"] else None
                    },
                    "ReviewDate": {
                        "date": {"start": data["ReviewDate"]} if data["ReviewDate"] else None
                    },
                    "Reason": {
                        "rich_text": [{"text": {"content": data["Reason"][:2000]}}] if data["Reason"] else []
                    },
                    "Knowledge": {
                        "rich_text": [{"text": {"content": data["Knowledge"][:2000]}}] if data["Knowledge"] else []
                    },
                    "ErrorCause": {
                        "rich_text": [{"text": {"content": data["ErrorCause"][:2000]}}] if data["ErrorCause"] else []
                    },
                    "Pitfall": {
                        "rich_text": [{"text": {"content": data["Pitfall"][:2000]}}] if data["Pitfall"] else []
                    },
                    "Analysis": {
                        "rich_text": [{"text": {"content": data["Analysis"][:2000]}}] if data["Analysis"] else []
                    }
                }
            }

            # 清理值为 None 的字段
            payload["properties"] = {k: v for k, v in payload["properties"].items() if v is not None and v.get("select") != {"name": None}}

            response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
            
            if response.status_code == 200:
                print(f"✅ 成功写入: {title}")
                success_count += 1
            else:
                print(f"❌ 写入失败 ({title}): {response.text}")

    print(f"\n🎉 Notion 多题目拆分增量同步完成！本次共成功新增 {success_count} 条错题。")

if __name__ == "__main__":
    sync_to_notion()
