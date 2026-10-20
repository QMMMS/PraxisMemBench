"""Produce concrete VERL configuration files from caller-supplied resources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex

import yaml

from .agent import tool_specs
from .config import load_config, verl_overrides


TOOL_CLASSES = {
    "list_memory_files": "ListMemoryFilesTool", "read_memory": "ReadMemoryTool",
    "grep_memory": "GrepMemoryTool", "edit_memory": "EditMemoryTool", "save_raw": "SaveRawTool",
}


def prepare(config: dict, *, output: Path, dataset: Path, model: Path,
            canonical_states: Path, sandbox_root: Path, embedding_base_url: str,
            embedding_key_env: str = "PRAXISMEM_EMBEDDING_API_KEY",
            embedding_model: str | None = None, gpus: int = 8) -> dict:
    """Write a new config directory; preserve the supplied export byte-for-byte."""
    dataset = dataset.resolve()
    if (dataset / "opsd").is_dir():
        dataset = dataset / "opsd"
    files = [dataset / f"{task}.parquet" for task in ("update", "retrieval")]
    if not all(path.is_file() for path in files):
        raise ValueError("dataset must contain update.parquet and retrieval.parquet")
    if not model.is_dir() or not canonical_states.is_dir():
        raise ValueError("supply existing local model and canonical-state directories")
    if gpus < 1 or not embedding_base_url.strip() or not embedding_key_env.isidentifier():
        raise ValueError("invalid GPU count, embedding endpoint or credential variable name")
    output = output.resolve()
    if output.exists():
        raise ValueError("choose a new configuration output directory")
    runtime_path, agents_path, tools_path = (output / name for name in ("runtime.yaml", "agents.yaml", "tools.yaml"))
    runtime = {
        "sandbox_root": str(sandbox_root.resolve()),
        "canonical_states_root": str(canonical_states.resolve()),
        "embedding_base_url": embedding_base_url,
        "embedding_key_env": embedding_key_env,
        "embedding_model": embedding_model or config["model"]["embedding_model"],
        "embedding_dimensions": 1024, "embedding_batch_size": 64,
        "max_prompt_length": config["data"]["max_prompt_length"],
        "retrieval_call_cap": config["runtime"]["retrieval_call_cap"],
        "semantic_threshold": config["opsd"]["semantic_threshold"],
        "coverage_threshold": config["opsd"]["coverage_threshold"],
    }
    agents = [{"name": f"markdown_{task}_agent",
               "_target_": f"praxismem.training.verl_agents.Markdown{task.title()}AgentLoop",
               "runtime_config": str(runtime_path)} for task in ("update", "retrieval")]
    tools = {"tools": [
        {"class_name": "praxismem.training.verl_tools." + TOOL_CLASSES[spec["function"]["name"]],
         "config": {"type": "native"}, "tool_schema": spec} for spec in tool_specs("update")
    ]}
    options = verl_overrides(config)
    options.update({
        "data.train_files": [str(path) for path in files], "data.val_files": [],
        "data.val_batch_size": 1, "data.dataloader_num_workers": 0,
        "data.filter_overlong_prompts": False, "data.truncation": "error",
        "data.apply_chat_template_kwargs.enable_thinking": False,
        "actor_rollout_ref.model.path": str(model.resolve()),
        "actor_rollout_ref.ref.strategy": "fsdp2",
        "actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu": 1,
        "actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu": 1,
        "actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu": 1,
        "actor_rollout_ref.actor.ppo_epochs": 1,
        "actor_rollout_ref.actor.entropy_coeff": 0.0,
        "actor_rollout_ref.rollout.name": "vllm", "actor_rollout_ref.rollout.mode": "async",
        "actor_rollout_ref.rollout.calculate_log_probs": True,
        "actor_rollout_ref.rollout.max_model_len": 32768,
        "actor_rollout_ref.rollout.agent.agent_loop_config_path": str(agents_path),
        "actor_rollout_ref.rollout.agent.default_agent_loop": "markdown_update_agent",
        "actor_rollout_ref.rollout.multi_turn.enable": True,
        "actor_rollout_ref.rollout.multi_turn.tool_config_path": str(tools_path),
        "actor_rollout_ref.rollout.multi_turn.format": "qwen3_coder",
        "actor_rollout_ref.rollout.multi_turn.max_parallel_calls": 1,
        "actor_rollout_ref.rollout.multi_turn.max_user_turns": 30,
        "actor_rollout_ref.rollout.multi_turn.max_assistant_turns": 30,
        "trainer.use_v1": True, "trainer.v1.trainer_mode": "sync",
        "trainer.nnodes": 1, "trainer.n_gpus_per_node": gpus,
        "trainer.val_before_train": False, "trainer.test_freq": -1,
        "trainer.default_local_dir": str(output / "checkpoints"),
        "trainer.project_name": "PraxisMem", "trainer.experiment_name": output.name,
        "trainer.logger": ["console"],
    })
    trainer = {"defaults": ["ppo_trainer", "_self_"],
               "hydra": {"searchpath": ["pkg://verl.trainer.config"]}}
    for key, value in options.items():
        node = trainer
        *parts, last = key.split(".")
        for part in parts:
            node = node.setdefault(part, {})
        node[last] = value
    output.mkdir(parents=True)
    for path, data in ((runtime_path, runtime), (agents_path, agents), (tools_path, tools),
                       (output / "trainer.yaml", trainer)):
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    argv = ["python", "-m", "verl.trainer.main_ppo", "--config-path", str(output), "--config-name", "trainer"]
    result = {"config_directory": str(output), "launch_argv": argv,
              "launch_command_posix": shlex.join(argv),
              "status": "configured"}
    (output / "launch.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("configs/training.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--canonical-states", type=Path, required=True)
    parser.add_argument("--sandbox-root", type=Path, required=True)
    parser.add_argument("--embedding-base-url", required=True)
    parser.add_argument("--embedding-key-env", default="PRAXISMEM_EMBEDDING_API_KEY")
    parser.add_argument("--embedding-model")
    parser.add_argument("--gpus", type=int, default=8)


def from_arguments(args) -> dict:
    return prepare(load_config(args.config), output=args.output, dataset=args.dataset,
                   model=args.model, canonical_states=args.canonical_states,
                   sandbox_root=args.sandbox_root, embedding_base_url=args.embedding_base_url,
                   embedding_key_env=args.embedding_key_env, embedding_model=args.embedding_model, gpus=args.gpus)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(from_arguments(args), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
