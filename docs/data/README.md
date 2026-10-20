# Datasets

The release uses two Hugging Face dataset repositories:

| Dataset | Contents |
| --- | --- |
| [PraxisMemBench](https://huggingface.co/datasets/QMMMS/PraxisMemBench) | `train.tar.gz` and `test.tar.gz` |
| [PraxisMem-Training](https://huggingface.co/datasets/QMMMS/PraxisMem-Training) | VERL training export and canonical state shards in `verl.tar.gz` |

Download the benchmark data:

```bash
pmb download --repository QMMMS/PraxisMemBench --output data/benchmark
```

Each benchmark archive extracts into its split directory:

```text
data/benchmark/
  train/
    trajectories/
    personas/
    conversation_history/
  test/
    trajectories/
    personas/
    conversation_history/
```

A trajectory contains `index.yaml`, a session directory and memory-metric
eligibility annotations. Each session provides the user script, scenario,
application fixtures and evaluation files. Task execution receives public
dialogue and the configured applications; scoring reads the evaluation files
after execution.

For training, download
[`verl.tar.gz`](https://huggingface.co/datasets/QMMMS/PraxisMem-Training/resolve/main/verl.tar.gz)
and extract it into `data/training/`. Use the resulting `data/training/verl/`
directory as the training export root.

The PraxisMem training export contains 481 Update samples and 1,440 Retrieval
samples. Each sample has a unique `sample_id`; several samples may share a
trajectory, session, and checkpoint. Initial Markdown files and task targets
are embedded in the Parquet rows; the online manager supplies the current
system prompt. See the [training guide](../training/README.md) for the schema
and validation commands.

