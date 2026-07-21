import json
import re

count = 0
wrong_count =0
with open(r"output_with_secure_cot.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(len(data))
for item in data:
    syn_output = item["secure_cot" ]
    # Extract content inside <secure_output> tags
    syn_output1 = syn_output.split("<secure_output>")[1].split("</secure_output>")[0]
    safe_label = item["safe_label"]
    if safe_label != syn_output1:
        # Remove this item
        wrong_count+=1
        data.remove(item)

    # Ensure syn_output strictly follows the format <secureCOT>...</secureCOT><secure_output>...</secure_output>
    cot_match = re.search(r"<secureCOT>(.*?)</secureCOT>", syn_output, re.DOTALL)
    cot = cot_match.group(1).strip() if cot_match else print("No match found")

    # Extract content inside <secure_result> tags
    result_match = re.search(r"<secure_output>(.*?)</secure_output>", syn_output, re.DOTALL)
    result = result_match.group(1).strip() if result_match else print("No match found")
    new_one = f"<secureCOT>{cot}</secureCOT>\n<secure_output>{result}</secure_output>"
    if new_one != item["secure_cot"]:
       count += 1
       print(new_one)
       item["secure_cot"]= new_one

print(len(data))
with open(r"output——filtered.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
print("ss",count)
print("move",wrong_count)