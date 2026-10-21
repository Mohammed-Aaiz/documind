# Structure evaluation report — structure-eval-v2

- Harness: structure-eval-harness-v1
- Top-K: 5
- Offline: yes (no PostgreSQL / pgvector / model)

## A_semantic_only

- Questions: 9

| metric | value |
|---|---|
| recall@5 | 0.8571 |
| precision@5 | 0.2071 |
| mrr | 0.8571 |
| ndcg@5 | 0.8571 |
| exact_match | 0.4286 |
| token_f1 | 0.6143 |
| answer_accuracy | 0.7143 |
| page_grounding | 1.0000 |
| section_grounding | 0.8571 |
| evidence_type_coverage | 1.0000 |
| answer_source_grounded | 0.8571 |
| answer_corpus_grounded | 1.0000 |
| unsupported_answer_rate | 1.0000 |
| semantic_source_count | 4.7778 |
| structural_source_count | 0.0000 |

## B_dual_path_chunk

- Questions: 9

| metric | value |
|---|---|
| recall@5 | 1.0000 |
| precision@5 | 0.4738 |
| mrr | 0.9286 |
| ndcg@5 | 0.9447 |
| exact_match | 0.4286 |
| token_f1 | 0.6143 |
| answer_accuracy | 0.7143 |
| page_grounding | 1.0000 |
| section_grounding | 0.8571 |
| evidence_type_coverage | 1.0000 |
| answer_source_grounded | 0.8571 |
| answer_corpus_grounded | 1.0000 |
| unsupported_answer_rate | 1.0000 |
| semantic_source_count | 3.4444 |
| structural_source_count | 0.0000 |

## C_structure_aware

- Questions: 9

| metric | value |
|---|---|
| recall@5 | 1.0000 |
| precision@5 | 0.3405 |
| mrr | 0.9048 |
| ndcg@5 | 0.9387 |
| exact_match | 0.4286 |
| token_f1 | 0.6143 |
| answer_accuracy | 0.7143 |
| page_grounding | 1.0000 |
| section_grounding | 1.0000 |
| evidence_type_coverage | 1.0000 |
| answer_source_grounded | 0.8571 |
| answer_corpus_grounded | 1.0000 |
| unsupported_answer_rate | 1.0000 |
| semantic_source_count | 0.0000 |
| structural_source_count | 4.0000 |

## D_fused_dual_path

- Questions: 9

| metric | value |
|---|---|
| recall@5 | 1.0000 |
| precision@5 | 0.5333 |
| mrr | 0.9048 |
| ndcg@5 | 0.9387 |
| exact_match | 0.4286 |
| token_f1 | 0.6143 |
| answer_accuracy | 0.7143 |
| page_grounding | 1.0000 |
| section_grounding | 0.8571 |
| evidence_type_coverage | 1.0000 |
| answer_source_grounded | 0.8571 |
| answer_corpus_grounded | 1.0000 |
| unsupported_answer_rate | 1.0000 |
| semantic_source_count | 2.8889 |
| structural_source_count | 1.4444 |
