import json
import os
import argparse
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Input_sql", help="Path to the complete file (all files)")
    parser.add_argument("--schema_dir", help="The file from omni2000")
    parser.add_argument("--output_prompt", help="Where the prompts are saved")
    parser.add_argument("--output_mapping", help="Where the mapping is saved, for later data processing")
    parser.add_argument('--model_path', type=str, help='Path to the model')
    parser.add_argument('--output_path', type=str, help='Output file path')
    parser.add_argument('--batch_size', type=int, help='Batch size')
    parser.add_argument('--part', type=int, help='Split into two halves, 0 for the first half, 1 for the second half',
                        choices=[0, 1])
    return parser.parse_args()


PROMPT_TEMPLATE = """**Task Overview**
Your task is to create a high-quality natural language question based on a given SQL query and other information.

**Database**
{database_str}

**SQL Query**
Given SQL query:
'''sql
{sql}
'''

**Output Format**
Please structure your response as follows:
Q：['question'].

**Insturction**
1. Uses standard grammar and vocabulary.
- Example: ['Find all students older than 18 years and return their home addresses.']
2. Clearly describe the columns being selected by the SQL query.
3. Ensure the natural language question accurately captures the semantics of the SQL query, including conditions such as predicates, ORDER BY, and LIMIT clauses.

**Answer**
Let's proceed step by step"""


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

        sql_list = item["extracted_sql"]
        schema_str = load_schema(id, args.schema_dir)

        if not schema_str:
            print(f"[Skip] Missing schema for {db_id}")
            continue

        for sql_idx, sql in enumerate(sql_list):
            prompt = PROMPT_TEMPLATE.format(
                database_str=schema_str.strip(),
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
