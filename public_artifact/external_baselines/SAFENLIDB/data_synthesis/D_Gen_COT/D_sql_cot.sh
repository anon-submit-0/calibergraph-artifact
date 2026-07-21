python D_Gen_COT/syn/syn.py \
--Input_sql "C_output" \
--schema_dir "Database_dataset" \
--output_prompt "D_output_prompt(to present the prompt)" \
--output_mapping "D_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "D_output_sql" \
--part 0

python D_Gen_COT/syn/syn.py \
--Input_sql "C_output" \
--schema_dir "Database_dataset" \
--output_prompt "D_output_prompt(to present the prompt)" \
--output_mapping "D_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "D_output_sql" \
--part 1 

python D_Gen_COT/process/Correspond.py
python D_Gen_COT/process/extract.py
python D_Gen_COT/process/safe_COT_con.py
python D_Gen_COT/process/join.py
python D_Gen_COT/process/format_processor.py