# PraxisMem Training

Training uses VERL agent loops and native tool wrappers
alongside the state scorer, dynamic residual routing and joint GRPO/OPSD loss.
Update and Retrieval share Markdown prompts and tool schemas with evaluation.

## Prepare a Run

Download [`verl.tar.gz`](https://huggingface.co/datasets/QMMMS/PraxisMem-Training/resolve/main/verl.tar.gz)
from [PraxisMem-Training](https://huggingface.co/datasets/QMMMS/PraxisMem-Training)
and extract it into `data/training/`. Set `EXPORT_DIR` to `data/training/verl/`
and `CANONICAL_STATE_DIR` to `data/training/verl/canonical_states/`.

Install this package with its training extra in the pinned VERL environment.
Supply a local base-model directory, the training dataset, canonical
chunk-state shards, an embedding service and a writable sandbox directory.

```bash
praxismem prepare-verl --config configs/training.yaml \
  --output "$TRAIN_CONFIG_DIR" --dataset "$EXPORT_DIR" --model "$MODEL_DIR" \
  --canonical-states "$CANONICAL_STATE_DIR" --sandbox-root "$SANDBOX_DIR" \
  --embedding-base-url "$EMBEDDING_BASE_URL"
```

This produces `trainer.yaml`, `agents.yaml`, `tools.yaml`, `runtime.yaml` and
`launch.json` in a new output directory. The agent names are `markdown_update_agent` and
`markdown_retrieval_agent`.

The embedding credential is read from `PRAXISMEM_EMBEDDING_API_KEY` by default;
`--embedding-key-env` selects another variable name. Provision that variable on
each worker. Generated configuration stores the variable name only.
`--embedding-model` selects the service's model identifier.

Launch VERL with the generated configuration:

```bash
python -m verl.trainer.main_ppo --config-path "$TRAIN_CONFIG_DIR" --config-name trainer
```

## Offline Checks

```bash
praxismem config --config configs/training.yaml
praxismem verl-overrides --config configs/training.yaml
praxismem validate-data "$EXPORT_DIR/opsd/update.parquet"
praxismem validate-data "$EXPORT_DIR/opsd/retrieval.parquet"
python tools/validate_training_data.py --directory "$EXPORT_DIR"
praxismem check-verl-patch --checkout "$VERL_DIR" --patch docs/training/patches/verl_dynamic_residual_opsd_grpo.patch
```

Row validation checks embedded stores and task fields; the export validator adds
counts, sample identifiers, content hashes and reference safety. The dataset
contains 481 Update and 1,440 Retrieval examples.

Each row carries `extra_info.sample_id`. The export's `opsd/samples.jsonl`
records task type, row position, trajectory, session, checkpoint where applicable,
and a content hash. Multiple Retrieval samples may share a checkpoint.
When canonical states are bundled, the export validator also checks their state
hash chains, each Update sample's initial/gold states, and update target locations.

## Paper Defaults

| Setting | Value |
| --- | --- |
| Backbone / embedding model | Qwen3.5-9B / Qwen3-Embedding-0.6B |
| Rollouts / temperature / top-p / top-k | 8 / 1.0 / 1.0 / -1 |
| Prompt / response budget | 24,576 / 4,096 tokens |
| Optimizer | Full-parameter FSDP2, learning rate 1e-6 |
| Batch / mini-batch / training epochs | 8 / 8 / 1 |
| GRPO clip / reference-KL coefficient | 0.2 / 0.01 |
| Semantic / coverage thresholds | 0.7 / 0.7 |
| Wrong-location weight | 0.2 |
| OPSD peak / linear warmup | 0.05 / first 10% of steps |
| Retrieval tool-call cap | 30 |

The paper setting used one node with eight A100 GPUs. The generated configuration
uses synchronous V1 training, serialized memory tools and a 32,768-token model
limit, with explicit teacher-context overflow checks.

[VERL configuration and patch details](verl.md)
