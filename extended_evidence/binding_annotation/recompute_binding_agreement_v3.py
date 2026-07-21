#!/usr/bin/env python3
"""Compute agreement for binding-annotation-pack-v2.

Usage from the pack root:
  python3 internal_author_key/recompute_binding_agreement_v2.py \
    returns/binding_annotation_sheet_v2_annotatorA.csv \
    returns/binding_annotation_sheet_v2_annotatorB.csv \
    returns/binding_annotation_sheet_v2_annotatorC.csv
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path


ANSWER_COLUMN = "your_answer(A/B/C/D/E)"
CATEGORIES = "ABCDE"


def load_sheet(path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {row["item_id"]: row[ANSWER_COLUMN].strip().upper() for row in rows}


def main():
    if len(sys.argv) != 4:
        raise SystemExit("expected exactly three returned CSV paths")

    sheets = [load_sheet(path) for path in sys.argv[1:4]]
    key_path = Path(__file__).with_name("answer_key_v3.json")
    key_payload = json.loads(key_path.read_text(encoding="utf-8"))
    key = {row["item_id"]: row["correct_option"] for row in key_payload["items"]}
    ids = [row["item_id"] for row in key_payload["items"]]

    expected = set(ids)
    for index, sheet in enumerate(sheets, start=1):
        if set(sheet) != expected:
            missing = sorted(expected - set(sheet))
            extra = sorted(set(sheet) - expected)
            raise SystemExit(f"sheet {index}: missing={missing}, extra={extra}")
        invalid = {item: answer for item, answer in sheet.items() if answer not in CATEGORIES}
        if invalid:
            raise SystemExit(f"sheet {index}: invalid answers={invalid}")

    table = []
    for item_id in ids:
        counts = Counter(sheet[item_id] for sheet in sheets)
        table.append([counts.get(category, 0) for category in CATEGORIES])

    n_items = len(table)
    n_raters = len(sheets)
    p_category = [
        sum(row[column] for row in table) / (n_items * n_raters)
        for column in range(len(CATEGORIES))
    ]
    p_item = [
        (sum(count * count for count in row) - n_raters)
        / (n_raters * (n_raters - 1))
        for row in table
    ]
    observed = sum(p_item) / n_items
    expected_agreement = sum(value * value for value in p_category)
    fleiss_kappa = (
        (observed - expected_agreement) / (1 - expected_agreement)
        if expected_agreement < 1
        else 1.0
    )

    all_three_agree = 0
    majority_matches = 0
    e_votes = 0
    disagreements = []
    for item_id in ids:
        votes = [sheet[item_id] for sheet in sheets]
        counts = Counter(votes)
        majority, majority_count = counts.most_common(1)[0]
        if len(set(votes)) == 1:
            all_three_agree += 1
        if majority_count >= 2 and majority == key[item_id]:
            majority_matches += 1
        e_votes += votes.count("E")
        if len(set(votes)) > 1 or majority_count < 2 or majority != key[item_id]:
            disagreements.append(
                {
                    "item_id": item_id,
                    "votes": votes,
                    "majority": majority if majority_count >= 2 else None,
                    "released_option": key[item_id],
                }
            )

    result = {
        "version": "binding-annotation-pack-v3",
        "annotator_type": "independent_agents",
        "human_iaa_claim": False,
        "n_items": n_items,
        "n_raters": n_raters,
        "fleiss_kappa": round(fleiss_kappa, 6),
        "all_three_agree": all_three_agree,
        "all_three_agreement_rate": round(all_three_agree / n_items, 6),
        "majority_matches_released": majority_matches,
        "majority_accuracy": round(majority_matches / n_items, 6),
        "e_votes": e_votes,
        "e_vote_rate": round(e_votes / (n_items * n_raters), 6),
        "disagreements": disagreements,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

