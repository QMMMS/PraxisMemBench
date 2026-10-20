# VERL Configuration and Patch

## Upstream

The wrappers target VERL revision
`1bf9d2d76c244238e8219531c582819a6b407d47`.
The integration uses
[ToolAgentLoop](https://github.com/verl-project/verl/blob/1bf9d2d76c244238e8219531c582819a6b407d47/verl/experimental/agent_loop/tool_agent_loop.py)
and [BaseTool](https://github.com/verl-project/verl/blob/1bf9d2d76c244238e8219531c582819a6b407d47/verl/tools/base_tool.py).

`patches/verl_dynamic_residual_opsd_grpo.patch` applies to that exact revision.
It provides PraxisMem's joint GRPO/OPSD training support.

Check and apply the patch in the pinned VERL checkout:

```bash
praxismem check-verl-patch --checkout "$VERL_DIR" --patch "$PATCH_FILE"
git -C "$VERL_DIR" apply "$PATCH_FILE"
```

Set `PATCH_FILE` to the absolute path of the patch in this repository.

The generated recipe selects `joint_dynamic` with gating and synchronous V1
training.

## Generated Files

`praxismem prepare-verl` creates these references:

| File | Consumer |
| --- | --- |
| `trainer.yaml` | `verl.trainer.main_ppo`, inheriting upstream `ppo_trainer` |
| `agents.yaml` | `MarkdownUpdateAgentLoop` and `MarkdownRetrievalAgentLoop` |
| `tools.yaml` | Five native `praxismem.training.verl_tools` classes |
| `runtime.yaml` | Resource paths, embedding settings and scorer budgets |
| `launch.json` | Launch arguments and a POSIX command string |

