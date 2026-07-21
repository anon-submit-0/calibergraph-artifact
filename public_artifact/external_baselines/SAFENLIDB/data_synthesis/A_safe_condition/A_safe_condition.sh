
#Your_range_type(chose from column or cells)
python  A_safe_condition/syn/syn.py \
--model_path "Your_model_path" \
--db_dataset "Your_db_dataset" \
--ex_path "./ex.json" \
--range_type "column" \
--batch_size 16 \
--output_path "Your_output_path"

python  A_safe_condition/syn/syn.py \
--model_path "Your_model_path" \
--db_dataset "Your_db_dataset" \
--ex_path "./ex.json" \
--range_type "cells" \
--batch_size 16 \
--output_path "Your_output_path"

python A_safe_condition/process/ex_out.py