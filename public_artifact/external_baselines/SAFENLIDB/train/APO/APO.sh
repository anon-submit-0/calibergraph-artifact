python train/APO/meta/all_wrong.py
python train/APO/meta/safe_wrong.py
python train/APO/meta/sql_wrong.py
python train/APO/join_dpo.py

FORCE_TORCHRUN=1 llamafactory-cli train APO_config.yaml