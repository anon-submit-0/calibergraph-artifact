import os
import argparse
import json
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

def parse_args():
    parser = argparse.ArgumentParser(
        description="Greedy inference using vLLM"
    )
    parser.add_argument(
        "--model_name_or_path", required=True,
        help="Path to the pretrained model"
    )
    parser.add_argument(
        "--template", default="llama3",
        help="Chat template name to apply"
    )
    parser.add_argument(
        "--dataset", required=True,
        help="Path to dataset file (jsonl or txt) with prompts"
    )
    parser.add_argument(
        "--batch_size", type=int, default=8,
        help="Batch size for inference"
    )
    parser.add_argument(
        "--save_name", required=True,
        help="Path to save the inference outputs (jsonl)"
    )
    return parser.parse_args()

def load_prompts(path):
    prompts = []
    if path.endswith('.jsonl'):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                prompt = item.get('question') or item.get('prompt')
                if prompt:
                    prompts.append(prompt)
    else:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    prompts.append(line)
    return prompts

def main():
    args = parse_args()

    print(f"Loading tokenizer from: {args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True
    )

    print(f"Initializing vLLM LLM with model: {args.model_name_or_path}")
    llm = LLM(
        model=args.model_name_or_path,
        tensor_parallel_size=1,
        gpu_memory_utilization=0.9
    )

    os.system("nvidia-smi")

    # Load prompts
    print(f"Loading prompts from dataset: {args.dataset}")
    all_prompts = load_prompts(args.dataset)

    # Prepare sampling parameters (using greedy decoding)
    sampling_params = SamplingParams(
        temperature=0,  # No randomness
        top_p=1.0,  # Full probability distribution
        max_tokens=500
    )

    # Apply chat template to each prompt
    chat_prompts = []
    for prompt in all_prompts:
        formatted = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            template=args.template,
            add_generation_prompt=True,
            tokenize=False
        )
        chat_prompts.append(formatted)

    # Batchify prompts
    batches = [
        chat_prompts[i:i + args.batch_size]
        for i in range(0, len(chat_prompts), args.batch_size)
    ]

    results = []

    print(f"Starting inference with batch size {args.batch_size}...")
    for batch in tqdm(batches, unit="batch"):
        outputs = llm.generate(batch, sampling_params=sampling_params)
        for inp, out in zip(batch, outputs):
            text = out.outputs[0].text
            results.append({"input": inp, "output": text})

    # Save results to JSONL
    print(f"Saving results to: {args.save_name}")
    with open(args.save_name, 'w', encoding='utf-8') as fout:
        for entry in results:
            fout.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("Inference complete.")

if __name__ == "__main__":
    main()
