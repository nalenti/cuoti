import os
import re
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
TARGET_DIR = "study"

def get_notion_existing_pages(headers):
    """获取 Notion 数据库中已存在的页面标题及对应的 Page ID"""
    page_map = {}
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
            page_id = page.get("id")
            properties = page.get("properties", {})
            title_val = ""
            for key, val in properties.items():
                if val.get("type") == "title":
                    t_list = val.get("title", [])
                    if t_list:
                        title_val = "".join([x.get("plain_text", "") for x in t_list])
                    break
            if title_val:
                page_map[title_val] = page_id
                
        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break
            
    return page_map

def parse_multiple_questions(file_path):
    """解析文件：精准提取顶部属性，并按“错题 X”切分正文"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def extract_field(key, text):
        pattern = rf"{key}:\s*(.+?)(?=\s+(?:Child|Subject|ReviewDate|Reason|Knowledge|ErrorCause|Pitfall|Analysis):|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    base_data = {
        "Child": extract_field("Child", content),
        "Subject": extract_field("Subject", content),
        "ReviewDate": extract_field("ReviewDate", content),
        "Reason": extract_field("Reason", content),
        "Knowledge": extract_field("Knowledge", content),
        "ErrorCause": extract_field("ErrorCause", content),
        "Pitfall": extract_field("Pitfall", content),
        "Analysis": extract_field("Analysis", content),
    }

    raw_filename = os.path.splitext(os.path.basename(file_path))[0]
    parts = re.split(r'(?=错题\s*\d+[:：])', content)
    questions = []

    for part in parts:
        part = part.strip()
        if not part or not re.match(r'^错题\s*\d+[:：]', part):
            continue
        
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
    page_map = get_notion_existing_pages(headers)
    print(f"📊 Notion 中当前已存在 {len(page_map)} 条记录。")

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
            data = q["data"]

            # 构造统一的属性格式 (rich_text)
            properties = {
                "标题": {
                    "title": [{"text": {"content": title[:200]}}]
                }
            }

            if data["Child"]:
                properties["Child"] = {"rich_text": [{"text": {"content": data["Child"][:2000]}}]}
            if data["Subject"]:
                properties["Subject"] = {"rich_text": [{"text": {"content": data["Subject"][:2000]}}]}
            if data["ReviewDate"]:
                properties["ReviewDate"] = {"rich_text": [{"text": {"content": data["ReviewDate"][:2000]}}]}
            if data["Reason"]:
                properties["Reason"] = {"rich_text": [{"text": {"content": data["Reason"][:2000]}}]}
            if data["Knowledge"]:
                properties["Knowledge"] = {"rich_text": [{"text": {"content": data["Knowledge"][:2000]}}]}
            if data["ErrorCause"]:
                properties["ErrorCause"] = {"rich_text": [{"text": {"content": data["ErrorCause"][:2000]}}]}
            if data["Pitfall"]:
                properties["Pitfall"] = {"rich_text": [{"text": {"content": data["Pitfall"][:2000]}}]}
            if data["Analysis"]:
                properties["Analysis"] = {"rich_text": [{"text": {"content": data["Analysis"][:2000]}}]}

            # 💡 智能判断：如果页面已存在（甚至是空白的），直接更新它；如果不存在，则创建新页面
            if title in page_map:
                page_id = page_map[title]
                print(f"🔄 正在更新已有页面: {title}...")
                response = requests.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=headers,
                    json={"properties": properties}
                )
                action_type = "更新"
            else:
                print(f"✨ 正在创建新页面: {title}...")
                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": properties
                }
                response = requests.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json=payload
                )
                action_type = "新增"

            if response.status_code == 200:
                print(f"✅ 成功{action_type}: {title}")
                success_count += 1
            else:
                print(f"❌ {action_type}失败 ({title}): {response.text}")

    print(f"\n🎉 Notion 智能同步完成！本次共成功处理 {success_count} 条错题。")

if __name__ == "__main__":
    sync_to_notion()
