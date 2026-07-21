python train/Inference/beam_infer.py \
  --model_name_or_path Your_model_path\
  --template llama3 \
  --dataset path_to_QAtest \
  --beam_size 8 \
  --save_name output_path