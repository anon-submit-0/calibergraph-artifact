import json
import random
import argparse
import os
import re

from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams


def parse_args():
    parser = argparse.ArgumentParser(description='Generate aggressive SQL')
    parser.add_argument('--condition_path', type=str,
                        help='Path to the safe condition')
    parser.add_argument('--prompts_path', type=str,
                        help='Path to store prompts')
    parser.add_argument('--model_path', type=str,
                        help='Path to the model')
    parser.add_argument('--db_dataset', type=str,
                        help='Path to the database dataset')
    parser.add_argument('--ex_path', type=str,
                        help='Path to the example file')
    parser.add_argument('--output_path', type=str,
                        help='Path to save output')
    parser.add_argument('--batch_size', type=int,
                        help='Batch size')
    parser.add_argument('--prompts_per_type', type=int,
                        help='Number of prompts generated per attack type')
    return parser.parse_args()


def if_number(specific_column):
    # Define keywords for numeric types
    numeric_types = {'int', 'integer', 'real', 'float', 'double', 'decimal', 'numeric'}

    # Use regular expression to extract all columns (name, type)
    matches = re.findall(r'\b\w+\.(\w+)\s*\((\w+)\)', specific_column)

    # Check if the type is numeric
    for _, col_type in matches:
        if col_type.lower() in numeric_types:
            return True
    return False


def if_cells(specific_value):
    if specific_value == "None":
        return False
    return True


def get_prompt_template(attack_type, is_number, is_cells):
    with open(os.path.join(os.path.dirname(__file__), "prompt.json"), 'r', encoding="utf-8") as f:
        prompt_templates = json.load(f)

    template_key = ""
    # Set template key based on attack type
    if attack_type == "1":  # Boundary testing
        template_key = "Boundary"
    elif attack_type == "2":  # Aggregation inference
        template_key = "Aggregation"
    elif attack_type == "3":  # Extreme value sorting
        template_key = "Equivalence"
    elif attack_type == "4":  # Incremental localization
        template_key = "Incremental"
    elif attack_type == "5":  # Complement attack
        template_key = "Complement"
    elif attack_type == "6":  # Direct attack
        template_key = "Directly"
    elif attack_type == "7":
        template_key = "Violence"

    # Select template based on conditions
    if template_key in prompt_templates:
        if is_cells and is_number:
            return prompt_templates.get(template_key, {}).get("is_cells_and_number", "Default template")
        elif is_cells and not is_number:
            return prompt_templates.get(template_key, {}).get("is_cells_and_not_number", "Default template")
        elif not is_cells and is_number:
            return prompt_templates.get(template_key, {}).get("is_column_and_number", "Default template")
        else:
            return prompt_templates.get(template_key, {}).get("is_column_and_not_number", "Default template")
    else:
        return "Default template"


def get_example_key(secure_type):
    # Return corresponding example key based on secure type
    example_keys = {
        "1": "Boundary",
        "2": "Aggregation",
        "3": "Equivalence",
        "4": "Incremental",
        "5": "Complement",
        "6": "Direct",
        "7": "Violence"
    }
    return example_keys.get(secure_type, "")


def generate_prompt(attack_type, safe_condition, schema_str, exs):
    safe_con = safe_condition["safe_condition"]
    specific_column = safe_condition["specific_column"]
    specific_value = safe_condition["specific_value"]
    is_number = if_number(specific_column)
    is_cells = if_cells(specific_value)
    prompt_template = get_prompt_template(attack_type, is_number, is_cells)

    if prompt_template == "None":
        return 0

    example_key = get_example_key(attack_type)

    if example_key == "Boundary":
        if is_cells:
            ex_samples = [exs[example_key][2], exs[example_key][3]]
        else:
            ex_samples = [exs[example_key][0], exs[example_key][1]]
    elif example_key == "Violence":
        ex_samples = random.sample(exs.get(example_key, []), k=min(2, len(exs.get(example_key, []))))
    elif example_key == "Aggregation" or example_key == "Equivalence":
        if is_cells:
            exs_list = exs.get(example_key, [])
            exs_list = exs_list[1]
            ex_samples = random.sample(exs_list, k=min(2, len(exs_list)))
        else:
            exs_list = exs.get(example_key, [])
            exs_list = exs_list[0]
            ex_samples = random.sample(exs_list, k=min(2, len(exs_list)))
    else:
        ex_samples = random.sample(exs.get(example_key, []), k=min(2, len(exs.get(example_key, []))))

    if ex_samples == ["None"]:
        return 0
    if len(ex_samples) == 0:
        prompt_template = prompt_template.replace("{exs}", "\n")
    else:
        ex_string = ex_samples[0]
        if len(ex_samples) > 1:
            ex_string += "\n\n" + "There is another example" + "\n" + ex_samples[1]
        prompt_template = prompt_template.replace("{exs}", ex_string)

    schema_str = schema_str + "\n" + f"safe_condition: {safe_con}" + "\n" + f"specific_column: {specific_column}" + "\n" + f"specific_value: {specific_value}"

    # Replace placeholders in the template
    prompt = prompt_template.replace("{schema_str}", schema_str).replace("{specific_column}", specific_column).replace(
        "{specific_value}", specific_value)

    print(prompt)
    return prompt


def main():
    args = parse_args()
    lun = 0
    # Extract data from safe condition results
    with open(args.condition_path, 'r', encoding="utf-8") as f:
        safe_conditions = json.load(f)

    # Load example data
    with open(args.ex_path, 'r', encoding="utf-8") as f:
        exs = json.load(f)

    # Load database dataset
    with open(args.db_dataset, 'r', encoding="utf-8") as f:
        db_dataset = json.load(f)

    all_prompts = []
    all_labels = []
    all_ids = []

    # Generate prompts for each safe condition
    for i in range(len(safe_conditions)):
        if safe_conditions[i]:
            safe_condition = safe_conditions[i]
        else:
            continue
        schema_str = db_dataset[int(safe_condition["id"])]

        # Generate prompts for each attack type
        for attack_type in ["1", "2", "3", "4", "5"]:
            # Set label
            label_map = {
                "1": "Boundary",
                "2": "Aggregation",
                "3": "Equivalence",
                "4": "Incremental",
                "5": "Complement",
                "6": "Direct"
            }
            label = label_map.get(attack_type, "")

            # Generate multiple prompts for each attack type
            for _ in range(args.prompts_per_type):
                prompt = generate_prompt(attack_type, safe_condition, schema_str, exs)
                if prompt == 0:
                    continue
                if prompt:
                    all_prompts.append(prompt)
                    all_labels.append(label)
                    all_ids.append(safe_condition["id"])

    # Save prompts to file
    with open(args.prompts_path, "w", encoding="utf-8") as fw:
        fw.write(json.dumps(all_prompts, indent=2, ensure_ascii=False))

    # Save ids to separate file
    ids_path = os.path.join(os.path.dirname(args.prompts_path), "prompt_ids.json")
    with open(ids_path, "w", encoding="utf-8") as fw:
        fw.write(json.dumps(all_ids, indent=2, ensure_ascii=False))

    print(f"Generated {len(all_prompts)} prompts, saved successfully")
    print(f"Saved {len(all_ids)} prompt IDs, saved successfully")

    # Load model and tokenizer
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

    # Process in batches
    batches = [chat_prompts[i:i + batch_size] for i in range(0, len(chat_prompts), batch_size)]
    results = []

    # Batch inference
    for batch in tqdm(batches, unit="batch"):
        outputs = llm.generate(batch, sampling_params=sampling_params)
        for data, output, label in zip(batch, outputs, all_labels[len(results):len(results) + len(batch)]):
            raw_responses = output.outputs[0].text
            results.append({'label': label, 'input': data, 'output': raw_responses})

    # Save results
    if lun % 5 == 0:
        with open(args.output_path, "w", encoding="utf-8") as fw:
            fw.write(json.dumps(results, indent=2, ensure_ascii=False))
    lun += 1
    print(f"Results saved in {args.output_path}")


if __name__ == "__main__":
    main()
