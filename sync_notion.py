import os
import requests

# 从环境变量中读取 Notion 凭证
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# 本地存放错题的文件夹
TARGET_DIR = "study"

def get_notion_existing_titles(headers):
    """
    从 Notion 数据库中拉取所有现有的页面标题
    """
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
            # 假设你 Notion 数据库的主标题列名叫 "标题"（如果叫 Name 请自行修改）
            title_prop = properties.get("标题", {})
            title_array = title_prop.get("title", [])
            if title_array:
                title_text = title_array[0].get("text", {}).get("content", "")
                if title_text:
                    existing_titles.add(title_text)
                    
        # 处理分页（如果你的错题超过 100 条）
        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break
            
    return existing_titles

def main():
    if not NOTION_TOKEN or not DATABASE_ID:
        print("⚠️ 未检测到 NOTION_TOKEN 或 DATABASE_ID，跳过 Notion 同步。")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    print("🔍 正在获取 Notion 数据库中已有的错题清单...")
    existing_titles = get_notion_existing_titles(headers)
    print(f"📊 Notion 中当前已存在 {len(existing_titles)} 条错题记录。")

    # 扫描本地 study/ 目录下的所有 .md 文件
    if not os.path.exists(TARGET_DIR):
        print(f"📭 本地未找到 {TARGET_DIR} 目录")
        return

    local_files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.md')]
    print(f"📁 本地 study/ 目录下共发现 {len(local_files)} 个 Markdown 文件。")

    new_count = 0
    for file_name in local_files:
        # 去掉 .md 后缀作为题目标题
        title = file_name[:-3]

        # 差集比对：如果本地的标题不在 Notion 列表中，说明是新错题
        if title not in existing_titles:
            print(f"✨ 发现新错题（增量）: {title}，正在写入 Notion...")
            
            create_url = "https://api.notion.com/v1/pages"
            create_payload = {
                "parent": {"database_id": DATABASE_ID},
                "properties": {
                    "标题": {
                        "title": [
                            {
                                "text": {
                                    "content": title
                                }
                            }
                        ]
                    }
                }
            }

            res = requests.post(create_url, headers=headers, json=create_payload)
            if res.status_code == 200:
                print(f"✅ [{title}] 成功写入 Notion！")
                new_count += 1
            else:
                print(f"❌ [{title}] 写入失败: {res.text}")
        else:
            print(f"⏩ [{title}] 已存在于 Notion 中，跳过。")

    print(f"🎉 Notion 增量同步完成！本次共成功新增 {new_count} 条错题。")

if __name__ == "__main__":
    main()
