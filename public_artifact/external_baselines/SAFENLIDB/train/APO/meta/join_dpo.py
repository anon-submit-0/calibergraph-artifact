import json
import random

path_list = [
    r'DPO_1.json',
    r'DPO_2.json',
    r'DPO_3.json'
]
with open(path_list[0], 'r', encoding='utf-8') as f:
    data = json.load(f)
with  open(path_list[1], 'r', encoding='utf-8') as f:
    data2= json.load(f)
with open (path_list[2], 'r', encoding='utf-8') as f:
    data3= json.load(f)
min_len = min(len(data2), len(data3))
data2_2 = random.sample(data2, 1000)
data3_3 = random.sample(data3, min_len)
new = []
new.extend(data)
for i in data2_2:
    print(i['chosen'])
    print(i['rejected'])
new.extend(data2_2)
new.extend(data3_3)
print(len(new))

with open(r'DPO_qwen_2k.json', 'w', encoding='utf-8') as f:
    json.dump(new, f, ensure_ascii=False)