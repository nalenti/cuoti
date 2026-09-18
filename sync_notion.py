import os
import re
import requests
import frontmatter  # 需要 pip install python-frontmatter

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
TARGET_DIR = "study"

def get_notion_existing_titles(headers):
    """查询 Notion 数据库中已存在的页面标题"""
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
            title_prop = properties.get("标题", {})
            title_array = title_prop.get("title", [])
            if title_array:
                title_text = title_array[0].get("text", {}).get("content", "")
                if title_text:
                    existing_titles.add(title_text)
                    
        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break
            
    return existing_titles

def md_text_to_notion_blocks(md_content):
    """将 Markdown 正文切分转换为 Notion Blocks"""
    blocks = []
    lines = md_content.split("\n")
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        if line_str.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line_str[2:].strip()}}]}
            })
        elif line_str.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line_str[3:].strip()}}]}
            })
        elif line_str.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line_str[4:].strip()}}]}
            })
        elif line_str.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": line_str[2:].strip()}}]}
            })
        elif line_str.startswith("- ") or line_str.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line_str[2:].strip()}}]}
            })
        elif line_str in ["---", "***", "___"]:
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
        else:
            content = line_str[:2000]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
            
    return blocks

def build_properties(title, metadata):
    """根据 Notion 实际数据库列名构造 payload"""
    properties = {
        "标题": {
            "title": [{"text": {"content": title}}]
        }
    }
    
    if "Child" in metadata:
        properties["Child"] = {
            "rich_text": [{"text": {"content": str(metadata["Child"])}}]
        }
        
    if "Subject" in metadata:
        properties["Subject"] = {
            "rich_text": [{"text": {"content": str(metadata["Subject"])}}]
        }
        
    if "ReviewDate" in metadata:
        properties["ReviewDate"] = {
            "rich_text": [{"text": {"content": str(metadata["ReviewDate"])}}]
        }

    if "Reason" in metadata:
        properties["Reason"] = {
            "rich_text": [{"text": {"content": str(metadata["Reason"])}}]
        }

    if "Knowledge" in metadata:
        knowledge_val = str(metadata["Knowledge"])
        tags = re.findall(r'#([^\s#]+)', knowledge_val)
        if tags:
            properties["Knowledge"] = {
                "multi_select": [{"name": tag} for tag in tags]
            }
        else:
            properties["Knowledge"] = {
                "multi_select": [{"name": knowledge_val[:100]}]
            }

    if "ErrorCause" in metadata:
        properties["ErrorCause"] = {
            "rich_text": [{"text": {"content": str(metadata["ErrorCause"])[:2000]}}]
        }

    if "Pitfall" in metadata:
        properties["Pitfall"] = {
            "rich_text": [{"text": {"content": str(metadata["Pitfall"])[:2000]}}]
        }

    if "Analysis" in metadata:
        properties["Analysis"] = {
            "rich_text": [{"text": {"content": str(metadata["Analysis"])[:2000]}}]
        }

    return properties

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

    if not os.path.exists(TARGET_DIR):
        print(f"📭 本地未找到 {TARGET_DIR} 目录")
        return

    local_files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.md')]
    print(f"📁 本地 {TARGET_DIR}/ 目录下共发现 {len(local_files)} 个 Markdown 文件。")

    new_count = 0
    for file_name in local_files:
        title = file_name[:-3]

        if title not in existing_titles:
            print(f"✨ 发现新错题（增量）: {title}，正在写入 Notion...")
            file_path = os.path.join(TARGET_DIR, file_name)
            
            try:
                post = frontmatter.load(file_path)
                metadata = post.metadata
                body_content = post.content
            except Exception as e:
                print(f"⚠️ 解析文件 {file_name} 失败: {e}")
                metadata = {}
                body_content = ""

            properties = build_properties(title, metadata)
            children_blocks = md_text_to_notion_blocks(body_content)
            
            create_payload = {
                "parent": {"database_id": DATABASE_ID},
                "properties": properties,
                "children": children_blocks[:100]
            }

            create_url = "https://api.notion.com/v1/pages"
            res = requests.post(create_url, headers=headers, json=create_payload)
            
            if res.status_code == 200:
                print(f"✅ [{title}] 成功完整写入 Notion！")
                new_count += 1
            else:
                print(f"❌ [{title}] 写入失败: {res.text}")
        else:
            print(f"⏩ [{title}] 已存在于 Notion 中，跳过。")

    print(f"🎉 Notion 增量同步完成！本次共成功新增 {new_count} 条错题。")

if __name__ == "__main__":
    main()
