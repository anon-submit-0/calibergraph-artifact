python C_NL_question_syn/syn/syn.py \
--Input_sql "B_output" \
--schema_dir "Database_dataset" \
--output_prompt "C_output_prompt(to present the prompt)" \
--output_mapping "C_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "C_output"\
--part 0

python C_NL_question_syn/syn/syn.py \
--Input_sql "B_output" \
--schema_dir "Database_dataset" \
--output_prompt "C_output_prompt(to present the prompt)" \
--output_mapping "C_output_mapping(to correspond)" \
--model_path   "Your_model_path" \
--batch_size 16 \
--output_path "C_output"\
--part 1

python C_NL_question_syn/process/Correspond.py
python C_NL_question_syn/process/Extract.py
python C_NL_question_syn/process/filter.py