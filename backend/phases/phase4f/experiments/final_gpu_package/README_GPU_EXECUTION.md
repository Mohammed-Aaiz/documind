# GPU Execution Package — Phase 4F.3

## Dataset
- Version: phase4f-qa-v3.1
- Examples: 918
- SHA-256: a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97

## Status
- **LOCAL GPU:** BLOCKED
- **EXTERNAL GPU:** REQUIRED
- **NO PRODUCTION MODEL REPLACEMENT:** YES

## Commands

```bash
pip install -r requirements.txt

# A1: DistilBERT
python training/train.py --experiment a1 --data_dir dataset --output_dir a1_distilbert

# A2: BERT-base
python training/train.py --experiment a2 --data_dir dataset --output_dir a2_bert_base

# A3: DeBERTa-v3
python training/train.py --experiment a3 --data_dir dataset --output_dir a3_deberta_v3

# Evaluate
python evaluation/evaluate.py --model_dir a1_distilbert --data_dir dataset
```

## Verify Before Training
```bash
python -c "import hashlib,json; d=json.load(open('dataset/training_data_v3_1.jsonl')); h=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:16]; print(f'Hash: {h}'); assert h=='a517530354fc9bca', 'HASH MISMATCH'"
```
