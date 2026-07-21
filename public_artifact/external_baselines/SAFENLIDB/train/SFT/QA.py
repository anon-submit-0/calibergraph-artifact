import json
import random
import re


def process_data(input_json_path, db_desc_path, output_path):
    # Read input data
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(len(data))
    # Read database description
    with open(db_desc_path, 'r', encoding='utf-8') as f:
        db_descriptions = json.load(f)
    output_list = []
    for item in data:
            # Get database description
            db_id = item['id']
            db_desc = db_descriptions[db_id]
            # Get question list and SQL list
            questions = item['questions']
            sql_list = item['sql_list']
            history = []
            for q, s in zip(questions[:-1], sql_list[:-1]):
                history.append({
                    "Q": q,
                    "A": s
                })
            safe_condition = item["safe_condition"]
            specific_column = item["specific_column"]
            specific_value = item["specific_value"]
            if len(history) == 0:
                chat_history = "The current question is the first question."
            else:
                history_items = []
                for idx, h in enumerate(history):
                    history_items.append(f"\nTurn-{idx + 1} :[ 'Question': {h['Q']}, 'SQL': {h['A']}]")
                chat_history = "".join(history_items)
            input_secure = f"""**Task Overview**
You are a Senior Data Analyst with deep expertise in SQL. When given:
1.A question from a front-end teammate
2.The corresponding database schema with safe condition
3.A concise chat history of prior discussion
your goal is to:
1.First, perform a security review against the schema and chat history.
If the question risks exposing restricted or sensitive fields or conditions, you must label the response as unsafe and stop—do not generate any SQL..
2.Remember, unless the current and previous queries together violate the security conditions, there's no need to refuse a response. 
**Database Schema** 
{db_desc}
safe_condition:{safe_condition}
**Chat history**
{chat_history}
**Output Format Requirements** 
To enable automated SQL extraction via regex, your reply must follow this exact format:
<secureCOT>
(Provide detailed reasoning here about whether it is safe to answer. Include any conditions checked, sensitive fields identified, etc.You can analysis in this way["first,I need to check and understand the safe_condition."...."Then,I need to figure out what can be infered or get from these queries."],which may help you.
</secureCOT>
<secure_output>(safe or unsafe)</secure_output>
<sql_COT>..</sql_COT>
**Question**
{questions[-1]}
**Answer** 
Let's proceed step by step."""
            output =  item["secure_cot"] +"<sql_COT>" + item["SQL_COT"][
                -1] + "\nThe ultimate answer is:\n```sql\n" + re.sub(r'\s+', ' ',
                                                                     item["sql_list"][-1]) + "\n```" + "</sql_COT>"

            output_list.append({

                        "instruction": input_secure,
                        "input": "",
                        "output": output
                    })
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_list, f, ensure_ascii=False, indent=4)
    return output_list

output_list = process_data(r"Cut_down1.json"
             ,r"omni_2000.json",
             r"QA_sql_safe.json")
print(len(output_list))