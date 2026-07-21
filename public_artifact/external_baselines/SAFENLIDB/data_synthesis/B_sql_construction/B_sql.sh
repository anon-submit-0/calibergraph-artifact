python syn_infer.py \
--condition_path "Your_condition_path(A_output)" \
--prompts_path "./prompts.json" \
--model_path "Your_model_path" \
--db_dataset "Your_db_dataset" \
--ex_path "./ex.json" \
--batch_size 16 \
--prompts_per_type 1 \
--output_path "./output_whole_column.json"\

python B_sql_construction/process/Merge_and_filter/pair.py
python B_sql_construction/process/Merge_and_filter/merge.py
python B_sql_construction/process/Rule_baed_construct/AR_replace.py
python B_sql_construction/process/Safe/omni.py
python B_sql_construction/process/Safe/soft_safe.py
python B_sql_construction/process/Merge_and_filter/CombineSQL.py
python B_sql_construction/process/filter/quality_control.py
