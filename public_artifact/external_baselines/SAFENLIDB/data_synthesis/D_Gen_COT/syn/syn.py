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


PROMPT_TEMPLATE = """You are a senior data analyst with deep expertise in SQL. Your task is to analyze the given natural language question and database schema, and produce a clear and detailed step-by-step reasoning process that would lead to the construction of an accurate SQLite query — without actually generating the SQL.
Only output the reasoning process, enclosed within <COT>...</COT> tags.
Format Example:
<COT>
Step-by-step reasoning here...
</COT>
Input:
[Database Schema]:
{database_str}
[Natural Language Question]: 
{question}
[Solution]: 
sql
{sql}
Now, generate the reasoning trace that would guide the construction of the SQL query."""


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
        schema_str = load_schema(id, args.schema_dir)
        question_list = item["questions"]

        for sql_idx, sql in enumerate(sql_list):
            question_i = question_list[sql_idx]

            prompt = PROMPT_TEMPLATE.format(
                database_str=schema_str.strip(),
                question=question_i.strip(),
                sql=sql.strip()
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
