import json
import re

# Read grouped_output.json
with open(r'output.json', 'r', encoding='utf-8') as f:
    data = json.load(f)


def extract_last_question(text):
    # Standardize newline characters
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    prefix_pattern = r'(?:\*\*Q[:：]\*\*|Q[:：]|\*\*Q:\*|Q\*\*:|Q\*\*:)'  # Prefix patterns for question marking

    # Match formats such as:
    # Q prefix followed by [xxx], or any question (ending with ? or .), multi-line allowed
    full_pattern = re.compile(
        rf'{prefix_pattern}\s*\n?\s*(\[[^\[\]]+?\]|.+?[?.])',
        re.IGNORECASE
    )

    matches = full_pattern.findall(text)

    if not matches:
        return None

    last = matches[-1].strip()

    # If in [xxx] format, remove brackets
    if last.startswith('[') and last.endswith(']'):
        last = last[1:-1].strip()

    # Remove any surrounding single quotes
    last = last.strip("'")
    return last


count = 0
# Extract questions from the 'output' field for each item
for item in data:
    item['questions'] = []
    for output in item['outputs']:
        question = extract_last_question(output)
        if question:
            item['questions'].append(question)
        else:
            print(f"No question found in output: {output}")
            count += 1
            item['questions'].append(
                "What are the names and email addresses of principals in schools with a student-teacher ratio greater than 15?")

# Save the results with extracted questions
print(f"Number of outputs without questions: {count}")
# Delete the 'outputs' field
for item in data:
    del item['outputs']

with open('extracted_questions111.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Questions have been extracted and saved in extracted_questions.json")
