python E_secure_COT/syn/syn.py \
--Input_sql "D_output" \
--schema_dir "Database_dataset" \
--output_prompt "E_output_prompt(to present the prompt)" \
--output_mapping "E_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "final_output" \
--part 0

python E_secure_COT/syn/syn.py \
--Input_sql "D_output" \
--schema_dir "Database_dataset" \
--output_prompt "E_output_prompt(to present the prompt)" \
--output_mapping "E_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "final_output" \
--part 1 

python E_secure_COT/process/pair.py
python E_secure_COT/process/filter.py
python E_secure_COT/process/Trigger.py
python E_secure_COT/process/u_filter.py