#!/usr/bin/env python3
"""Split rag_dataset into train/test sets using only llm_qa_pairs."""

import json
import random
from pathlib import Path

# Set seed for reproducibility
random.seed(42)

# Read all records from rag_dataset.jsonl
all_qa_pairs = []
records_with_llm_qa = 0

with open("docs/rag_dataset.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line.strip())
        llm_qa_pairs = record.get("llm_qa_pairs", [])

        # Only process records with non-empty llm_qa_pairs
        if llm_qa_pairs:
            records_with_llm_qa += 1
            all_qa_pairs.extend(llm_qa_pairs)

# Split into test (random 15) and train (rest)
total_pairs = len(all_qa_pairs)
test_count = min(15, total_pairs)

# Randomly select indices for test set
test_indices = set(random.sample(range(total_pairs), test_count))

test_pairs = []
train_pairs = []

for idx, pair in enumerate(all_qa_pairs):
    if idx in test_indices:
        test_pairs.append(pair)
    else:
        train_pairs.append(pair)

# Write test set
with open("docs/rag_dataset_test.jsonl", "w", encoding="utf-8") as f:
    for pair in test_pairs:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")

# Write train set
with open("docs/rag_dataset_train.jsonl", "w", encoding="utf-8") as f:
    for pair in train_pairs:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")

print(f"Records with llm_qa_pairs: {records_with_llm_qa}")
print(f"Total QA pairs extracted: {total_pairs}")
print(f"Test set: {len(test_pairs)} pairs")
print(f"Train set: {len(train_pairs)} pairs")
