import json
import re

# Read grouped_output.json
with open('grou_output.json', 'r', encoding='utf-8') as f:
    data = json.load(f)


def extract_last_question(text):
    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Match content between <COT> and </COT> tags
    full_pattern = re.compile(r'<COT>(.*?)</COT>', re.IGNORECASE | re.DOTALL)

    matches = full_pattern.findall(text)

    if not matches:
        return None

    last = matches[-1].strip()

    return last

count = 0
# Extract questions from output for each group
for item in data:
    item['SQL_COT'] = []
    for output in item['outputs']:
        question = extract_last_question(output)
        item['SQL_COT'].append(question)
        if question:
            count += 0
        else:
            del item
            count += 1
            break

print(f"Number of missing questions: {count}")
# Remove output key
for item in data:
    del item['outputs']

with open('01.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Questions extracted and saved in extracted_questions.json")
