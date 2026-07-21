import json

JSON_PATH    = r'dev.json'    # Path to dev.json
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
db_id = []
for item in data:
    if item['safe_label'] == 'safe':
        db_id.append(item['db_id'])
with open('db_id.json', 'w', encoding='utf-8') as f:
    json.dump(db_id, f, ensure_ascii=False, indent=4)
