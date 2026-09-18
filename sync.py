import os
import requests
import json

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def extract_value(prop):
    if not prop:
        return ""
    p_type = prop.get("type")
    if p_type == "title":
        t = prop.get("title", [])
        return "".join([x.get("plain_text", "") for x in t])
    elif p_type == "rich_text":
        rt = prop.get("rich_text", [])
        return "".join([x.get("plain_text", "") for x in rt])
    elif p_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    elif p_type == "date":
        d = prop.get("date")
        return d.get("start", "") if d else ""
    elif p_type == "multi_select":
        ms = prop.get("multi_select", [])
        return ", ".join([x.get("name", "") for x in ms])
    return ""

def sync_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    results = []
    has_more = True
    start_cursor = None

    print("正在从 Notion 循环拉取所有错题数据...")
    
    # 💡 核心修改：通过 while 循环进行分页拉取，突破 100 条限制
    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Error querying Notion: {response.text}")
            return

        res_data = response.json()
        results.extend(res_data.get("results", []))
        
        has_more = res_data.get("has_more", False)
        start_cursor = res_data.get("next_cursor")

    print(f"成功拉取到共计 {len(results)} 条记录，正在处理字段...")
    data_list = []

    for page in results:
        props = page.get("properties", {})
        
        # 智能寻找标题列
        title_val = ""
        for key, val in props.items():
            if val.get("type") == "title":
                title_val = extract_value(val)
                break
        if not title_val:
            title_val = extract_value(props.get("标题") or props.get("Title") or props.get("Name"))

        # 整合错误原因内容
        error_content = extract_value(props.get("Error") or props.get("ErrorCause") or props.get("Reason"))

        item = {
            "Title": title_val,
            "Child": extract_value(props.get("Child")),
            "Subject": extract_value(props.get("Subject") or props.get("科目")),
            "ReviewDate": extract_value(props.get("Review Date") or props.get("ReviewDate")),
            "Reason": error_content,
            "Error": error_content,
            "ErrorCause": error_content,
            "Knowledge": extract_value(props.get("Knowledge")),
            "Analysis": extract_value(props.get("Analysis")),
            "Pitfall": extract_value(props.get("Pitfall"))
        }
        data_list.append(item)

    with open("jamie-data.json", "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    print(f"Successfully updated jamie-data.json (总计写入 {len(data_list)} 条数据)")

if __name__ == "__main__":
    sync_notion_data()
