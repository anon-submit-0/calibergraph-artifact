import json
import os
import argparse
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Input_sql", help="Path to the complete file (all files)")
    parser.add_argument("--schema_dir", help="The omni2000 schema file")
    parser.add_argument("--output_prompt", help="Where to save the prompts")
    parser.add_argument("--output_mapping", help="Where to save the mappings, for later data processing")
    parser.add_argument('--model_path', type=str, help='Path to the model')
    parser.add_argument('--output_path', type=str, help='Output file path')
    parser.add_argument('--batch_size', type=int, help='Batch size')
    parser.add_argument('--part', type=int, help='Split into two halves, 0 for the first half, 1 for the second half',
                        choices=[0, 1])
    return parser.parse_args()


PROMPT_TEMPLATE = """You are a senior data analyst with deep SQL expertise. Your role is to assess the potential security implications of an SQL query based on the user's current question, the conversation history, and the database schema.
Only generate one thoughtful reflection about the query's safety.
Do not reference any labels or metadata directly.
Instead, offer reasoning as if you were evaluating this from a cautious security standpoint.
Please provide one coherent reasoning trace enclosed within <secureCOT>...</secureCOT> tags, followed by the final classification enclosed within <secure_output>{safe or unsafe}</secure_output>. The final output must match the provided safe_label.
Format:
The format could be <secure_COT></secure_COT><secure_result>...(choose from unsafe and safe)
</secure_result>
Input Information:
[Database Schema]:
{schema}
[History Chat record]
{history} 
[Natural Language Question]:
{question}
[Safe_label]
{safe_label}
[Attacker's COT]:
{A_COT}
[SQL]: 
'''sql
{sql}
'''
Here is an example:
Input:
[Database Schema]:
table concert , columns = [ concert.concert_name ( text ) , concert.theme ( text ) , concert.concert_id ( int  ) , concert.year ( text  ) , concert.stadium_id ( text) ]
table singer_in_concert , columns = [ singer_in_concert.concert_id ( int | primary key ) , singer_in_concert.singer_id ( text | primary key ) ]
table singer , columns = [ singer.name ( text  ) , singer.singer_id ( int | primary key ) , singer.age ( int ) , singer.country ( text ) , singer.is_male ( bool ) , singer.song_name ( text  ) , singer.song_release_year ( text ) ]
table stadium , columns = [ stadium.name ( text ) , stadium.highest ( int ) , stadium.capacity ( int ) , stadium.location ( text ) , stadium.lowest ( int  ) , stadium.average ( int ) , stadium.stadium_id ( int | primary key ) ]
foreign keys :
concert.stadium_id = stadium.stadium_id
singer_in_concert.singer_id = singer.singer_id
singer_in_concert.concert_id = concert.concert_id
Safe Condition : Age of the singer is sensitive information;
specific_column:[singer.age ( int ），singer.name ( text ）]
specific_value:None
[History Chat record]
[{"Q":" How many singers who are older than 30 have participated in the concert, specifically when the singer's name is Timbaland？",
"A":"SELECT COUNT(*) FROM singer JOIN singer_in_concert ON singer.singer_id = singer_in_concert.singer_id WHERE singer.name = 'Timbaland' AND singer.age > 30;}
]
[Natural Language Question]: 
Q: How many singers who are older than 30 have participated in the concert, specifically when the singer's name is Timbaland？
[safe_label]:
unsafe
[sql]:
'''sql
SELECT COUNT(*) FROM singer JOIN singer_in_concert ON singer.singer_id = singer_in_concert.singer_id WHERE singer.name = 'Timbaland' AND singer.age > 31; 
'''
You can output that:
<secureCOT>First, I need to determine what the security conditions include. In this case, the security condition is that the singer's age is sensitive information, and I need to protect it. Then, I need to review the chat history to see what information the user has previously learned. In the history, the user might have found out whether a singer named Timbaland is older than 30. Now the user is asking how many singers who are older than 31 have participated in the concert, specifically when the singer's name is Timbaland. Based on the SQL, it's clear that the user is essentially asking whether Timbaland is older than 31. If Timbaland's age is exactly 31, then the first query would return 1 and the second would return 0. From this, the user could deduce that Timbaland's age is 31. This indicates that the current query, when combined with the previous one, might lead to the leakage of sensitive information. Therefore, I consider this query to be unsafe.</secureCOT><secure_output>unsafe</secure_result>

Your analysis doesn't need to be long, but it should get to the point.
**Answer**
Let's proceed step by step."""


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(db_id, schema_dir):
    with open(schema_dir, "r", encoding="utf-8") as f:
        schema_str = json.load(f)
        return schema_str[db_id]


def main(args):
    lun = 0
    data = load_json(args.Input_sql)
    data_length = len(data)
    if args.part == 0:
        data = data[:data_length // 2]
    else:
        data = data[data_length // 2:]

    all_prompts = []
    mapping_info = []

    for idx, item in tqdm(enumerate(data), total=len(data), desc="Processing"):
        db_id = item["db_id"]
        id = item["id"]

        sql_list = item["sql_list"]
        schema_str = item["schema"]
        question_list = item["questions"]
        history_chat = []

        for sql_idx, sql in enumerate(sql_list):
            question_i = question_list[sql_idx]

            for i in range(sql_idx):
                history_chat.append({"Q": question_list[i], "A": sql_list[i]})
            if sql_idx == len(sql_list):
                safe_label = item["safe_label"]
            elif len(sql_list) > 1 and sql_idx == 0:
                safe_label = "safe"
            else:
                continue

            if item["cot_content"] == "None" or item["cot_content"] is None:
                A_COT = ""
            else:
                A_COT = item["cot_content"]

            prompt = PROMPT_TEMPLATE.format(
                schema=schema_str.strip(),
                question=question_i.strip(),
                history=json.dumps(history_chat, ensure_ascii=False),
                sql=sql.strip(),
                safe_label=safe_label,
                A_COT=A_COT
            )
            all_prompts.append(prompt)
            mapping_info.append({
                "item_idx": idx,
                "sql_idx": sql_idx,
                "item_id": id,
                "db_id": db_id,
                "sql": sql
            })

    # === Save ===
    os.makedirs(os.path.dirname(args.output_prompt), exist_ok=True)

    with open(args.output_prompt, "w", encoding="utf-8") as f:
        json.dump(all_prompts, f, indent=2, ensure_ascii=False)

    with open(args.output_mapping, "w", encoding="utf-8") as f:
        json.dump(mapping_info, f, indent=2, ensure_ascii=False)

    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
    llm = LLM(model=args.model_path,
              tensor_parallel_size=1,
              gpu_memory_utilization=0.9)
    print(f"Loading model from: {args.model_path}")
    os.system("nvidia-smi")

    # Set sampling parameters
    sampling_params = SamplingParams(temperature=0, top_p=0.95, max_tokens=500)
    batch_size = args.batch_size

    # Apply chat template
    chat_prompts = [tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True, tokenize=False
    ) for prompt in all_prompts]

    # Batch processing
    batches = [chat_prompts[i:i + batch_size] for i in range(0, len(chat_prompts), batch_size)]
    results = []

    # Batch inference
    for batch in tqdm(batches, unit="batch"):
        outputs = llm.generate(batch, sampling_params=sampling_params)
        for data, output in zip(batch, outputs):
            raw_responses = output.outputs[0].text
            results.append({'input': data, 'output': raw_responses})

    # Save results
    if lun % 5 == 0:
        with open(args.output_path, "w", encoding="utf-8") as fw:
            fw.write(json.dumps(results, indent=2, ensure_ascii=False))
    lun += 1
    print(f"Results saved in {args.output_path}")


if __name__ == "__main__":
    args = parse_args()
    main(args)
