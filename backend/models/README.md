# DocuMind QA Model Directory

This directory should contain the trained DocuMind QA model artifacts.

## Required Files

Place the following files in the `documind-qa` subdirectory:

- `config.json` - Model configuration
- `model.safetensors` or `pytorch_model.bin` - Model weights
- `tokenizer.json` - Tokenizer configuration
- `tokenizer_config.json` - Tokenizer settings
- `special_tokens_map.json` - Special tokens mapping
- `vocab.json` or `tokenizer.model` - Vocabulary file

## Example Structure

```
models/
└── documind-qa/
    ├── config.json
    ├── model.safetensors
    ├── tokenizer.json
    ├── tokenizer_config.json
    ├── special_tokens_map.json
    └── vocab.json
```

## Configuration

Set the `QA_MODEL_NAME` environment variable to point to this directory:

```bash
QA_MODEL_NAME=./models/documind-qa
```

Or in the `.env` file:

```
QA_MODEL_NAME=./models/documind-qa
```

## Important Notes

- The model directory must contain all necessary files for `AutoModelForQuestionAnswering` and `AutoTokenizer`
- The application will not start the QA endpoint if the model is not found
- Do NOT use external pre-trained models - only the trained DocuMind model should be used
