# Concatenate two JSON files directly

import json

with open('part_0.json', 'r', encoding='utf-8') as f:
    data1 = json.load(f)
with open('part_1.json', 'r', encoding='utf-8') as f:
    data2 = json.load(f)


data1.extend(data2)
with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(data1, f, ensure_ascii=False, indent=4)
