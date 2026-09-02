---
name: prompt-optimizer
description: Local, agent-orchestrated prompt optimizer for structured, measurable tasks. Use when you (the calling agent) have a prompt, a human gold-answer evaluation set (JSONL/CSV/Excel), and a plain-language business goal, and need to iteratively improve the prompt with deterministic metric-backed evidence. Inference is performed by the user's target model via the `run-inference` CLI tool — you never produce predictions yourself. You orchestrate eval planning, attribution, rewrite, and strategy steps; the bundled Python tools handle deterministic scoring, metric computation, and guardrail checks. Reject open writing, marketing copy, creative polishing, chat personas, multi-step agent workflows, and any prompt without stable gold-answer evaluation data.
---

# Prompt Optimizer

This Skill optimizes a structured prompt against a human gold-answer evaluation set. The work is split by a single principle:

**Deterministic work → `python_cli`. Understanding work → `agent`. Inference → `llm_api` (the user's target model).**

You orchestrate the whole loop. You read the prompt templates in `assets/prompts/`, reason over the data, and produce judgements yourself. For inference (running the prompt over the dataset to get predictions), you call `run-inference` which invokes the **user's specified model** via API — you never produce predictions yourself. You call the other bundled tools for scoring, metrics, and guardrails.

The inference tool calls the user's real model. **You are not the model being evaluated.** Your role is orchestration and understanding (eval plan, attribution, rewrite, strategy). Predictions come from the target model so the optimization result is valid for the model the user will actually deploy.

## When To Use

Use only when all are true:

- The task has a structured, checkable answer shape: classification, tagging, quality judgement, structured extraction, or rubric scoring.
- The user can provide human gold answers in JSONL, CSV, or Excel.
- The business goal is statable in plain language (e.g. prioritize recall, precision, field completeness, scoring consistency).

Reject or ask for the missing input when:

- There is no gold-answer evaluation set.
- The prompt is for open writing, marketing copy, creative polishing, long-form summarization, chat persona behavior, or a multi-step agent workflow.
- The desired output cannot be judged by a stable, deterministic rule.

## Skill Layout

```
prompt_optimize/
├── SKILL.md                         # this file — your orchestration spec
├── assets/
│   ├── requirements.txt             # runtime dependencies
│   ├── .env.example                 # env var template for API keys
│   └── prompts/                     # LLM step templates you read and execute
└── scripts/
    ├── run_prompt_optimizer.py      # CLI wrapper (call by absolute path)
    └── prompt_optimizer/
        ├── cli.py                   # subcommand dispatch
        └── tools/                   # deterministic + inference
            ├── dataset.py
            ├── scorer.py
            ├── metrics.py
            ├── guardrail.py
            └── inference.py
```

## Prerequisites

Install runtime dependencies before first use:

```bash
pip install -r $SKILL/assets/requirements.txt
```

## The Deterministic Tools (CLI)

Call by absolute path so it works from any working directory. Let `SKILL=<skill-dir>`:

```bash
python $SKILL/scripts/run_prompt_optimizer.py <subcommand> [args]
```

Every subcommand prints JSON to stdout. Predictions/results args accept a `.jsonl` path, a `.json` path, or an inline JSON string.

| Subcommand | Purpose | Key args |
|---|---|---|
| `validate-inputs` | Check format + that every row has a gold answer. Returns `{valid, row_count, sample_rows, error}`. **Does not infer task_type.** | `--dataset` `[--input-column] [--gold-column] [--sample-size]` |
| `split-dataset` | Stratified train/holdout split (fallback when no separate test set). Optimize on train; report on holdout. | `--dataset` `[--holdout-ratio] [--train-out] [--holdout-out] [--input-column] [--gold-column]` |
| `load-dataset` | Load + normalize all rows. With `--strip-gold`, output only `{id, input}` for inference. | `--dataset` `[--input-column] [--gold-column] [--strip-gold]` |
| `run-inference` | Call the user's target model API to produce predictions. Never sees gold. API key is auto-resolved from env vars / `.env` file; `--api-key` is optional (env var name or literal fallback). | `--prompt` `--dataset` `--model` `[--api-key]` `[--base-url] [--prompt-mode] [--concurrency] [--timeout] [--output]` |
| `score-predictions` | Judge `is_correct` per row by task_type rule. Can merge gold from `--dataset`. | `--task-type` `--predictions` `[--dataset]` |
| `compute-metrics` | Compute ALL metrics in the task_type's pool. | `--task-type` `--results` |
| `check-guardrails` | Decide candidate `eligible` vs baseline. | `--payload` |

Scoring rules by `task_type`: classification/quality_judgement = exact string match; tagging = set equality; rubric_scoring = numeric equality; structured_extraction = field-set + per-field value match.

Metric pools (the eval plan you write picks primary/secondary from these — do not invent metrics outside the pool):

- classification / quality_judgement: `accuracy, macro_precision, macro_recall, macro_f1`
- tagging: `micro_precision, micro_recall, micro_f1, exact_match, label_regression_rate`
- structured_extraction: `field_accuracy, field_f1, missing_field_rate, extra_field_rate`
- rubric_scoring: `exact_match, within_1_accuracy, mae`

## Orchestration Flow

Inputs you start with: `prompt_text`, `dataset_path`, `business_goal`, `model` (target model ID), an output dir `OUT`, and `rounds` (default 10). Every step's output is written to an artifact under `OUT` — artifacts are the only state passed between steps, so any step can restart from the last successful artifact.

**Train vs holdout — decide this before optimizing.** The loop improves the prompt by repeatedly scoring candidates on the eval data and keeping what scores best. If you optimize and report on the *same* rows, the number you hand back measures fit to those specific rows, not generalization — a prompt can be tuned to the eval set's quirks (even its label noise) and still look great. So the optimization set (`TRAIN`) and the set you report the final number on (`HOLDOUT`) must be different:

- **Ask the user whether they already have a separate test/holdout set.** If yes, use their training data as `TRAIN` and their test data as `HOLDOUT` — this is always preferable to an automatic split.
- **If they only have one dataset, split it** (see Step 0.5). Tell the user you're holding out a slice they never optimize on, and why — it's the difference between a reported gain and a gain you can trust on new data.

Throughout the loop, `<dataset_path>` in the commands below means the **TRAIN** set. `HOLDOUT` is touched only once, in the final validation step.

**Model configuration is mandatory.** Before proceeding past Step 0, you must have the user's target model and a working API key. Do not fall back to using yourself (the orchestrating agent) for inference. The prompt is being optimized for the user's target model, not for you.

Executor key used in step annotations:

| Tag | Who | Examples |
|-----|-----|----------|
| `agent` | The orchestrating agent (you) | eval plan, attribution, rewrite, selection |
| `python_cli` | Python CLI (`run_prompt_optimizer.py`) | validate, score, metrics, guardrails |
| `llm_api` | Target model via `run-inference` | baseline predictions, candidate predictions |

Compound: `(llm_api → python_cli)` = call the target model, then pipe output to a Python CLI tool.

### Step 0 — Validate (python_cli) + confirm model config (agent)

```bash
python $SKILL/scripts/run_prompt_optimizer.py validate-inputs --dataset <dataset_path>
```

If `valid` is false, stop and report the `error` to the user (boundary/exit-2 situation). Otherwise keep `sample_rows` for the next step.

**Before continuing**: confirm model and API key are available. Follow this priority chain:

1. **Check env vars**: run `echo $DEEPSEEK_API_KEY` (or check other common key var names: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DASHSCOPE_API_KEY`). If a value exists, use it — no need to ask the user.
2. **Guide .env setup step-by-step (local agent)**: if no env var is found and you can write to the local filesystem:
   a. Ask the user for the target model name (e.g., `deepseek-chat`, `gpt-4o`, `claude-3-5-sonnet`) and whether they are using the official provider's API or a custom/proxy gateway.
   b. Judge the official provider by model keywords (e.g. `gpt` for OpenAI, `claude` for Anthropic, `deepseek` for DeepSeek, `qwen` for DashScope) or user input. Auto-configure the corresponding base URL:
      * **DeepSeek**: `https://api.deepseek.com` (Env key: `DEEPSEEK_API_KEY`)
      * **OpenAI**: `https://api.openai.com/v1` (Env key: `OPENAI_API_KEY`)
      * **Anthropic**: `https://api.anthropic.com` (Env key: `ANTHROPIC_API_KEY`)
      * **DashScope / Qwen**: `https://dashscope.aliyuncs.com/compatible-mode/v1` (Env key: `DASHSCOPE_API_KEY`)
      If a custom endpoint or company gateway is used, ask the user to provide the base URL.
   c. Write/create the `.env` file in the project root with the `TARGET_MODEL`, `TARGET_BASE_URL` (if applicable), and the appropriate API key variable name (e.g., `DEEPSEEK_API_KEY=`, `OPENAI_API_KEY=`), leaving the value blank.
   d. Guide the user to manually fill in the key: "我已经为你生成了 `.env` 文件。出于安全考虑，请你手动打开项目根目录下的 `.env` 文件，并在对应位置填入你的 API Key。"
3. **Guide platform Secrets (cloud agent)**: if you cannot access or write to the local filesystem (running in cloud), guide the user to configure env vars in their cloud platform's Secrets/Environment settings.
4. **Accept plaintext (fallback)**: if the user directly provides an API key in plaintext, accept it and proceed.

**Important**: when constructing `run-inference` commands, pass the env var **name** (not the value) to `--api-key` so that the actual key does not appear in command lines or logs:
```bash
--api-key DEEPSEEK_API_KEY   # ✅ pass the env var name
--api-key sk-abc123...       # ⚠️ works but exposes key in logs
```

### Step 0.5 — Establish train/holdout (agent + python_cli)

Ask the user if they have a separate test/holdout set.

- **They do**: set `TRAIN` = their training file, `HOLDOUT` = their test file. Skip the split.
- **They don't** (one dataset only): split it, stratified by gold answer so every label shape appears on both sides:

```bash
python $SKILL/scripts/run_prompt_optimizer.py split-dataset \
  --dataset <dataset_path> --holdout-ratio 0.2 \
  --train-out OUT/train.jsonl --holdout-out OUT/holdout.jsonl
```

Then `TRAIN` = `OUT/train.jsonl`, `HOLDOUT` = `OUT/holdout.jsonl`. Report the split summary to the user (counts + ratio). If `split-dataset` exits 2 (every gold value is unique, so no stratum can be split), tell the user and ask for more rows per label or a separate test set — do not optimize without a holdout.

For the rest of the flow, use `TRAIN` wherever a command says `<dataset_path>`.

### Step 1 — Eval plan (agent) → `OUT/eval_plan.json`

Read `assets/prompts/eval_plan_generation.md`. Using `prompt_text`, `sample_rows`, and `business_goal`, decide `task_type`, `primary_metric`, `secondary_metrics`, `guardrails`, `confidence`. Do **not** decide task_type from the gold data type alone — combine prompt intent + business goal. Write the JSON to `OUT/eval_plan.json`. This runs once.

Then prepare inputs for inference (python_cli, gold-stripped):

```bash
python $SKILL/scripts/run_prompt_optimizer.py load-dataset --dataset <dataset_path> --strip-gold > OUT/inputs.jsonl
```

### Step 2 — Baseline (llm_api → python_cli) → `OUT/baseline_results.jsonl`, `OUT/baseline_metrics.json`

Call the user's target model to produce predictions. **You do not infer yourself** — the `run-inference` tool calls the real API:

```bash
python $SKILL/scripts/run_prompt_optimizer.py run-inference \
  --prompt <prompt_text_or_file> \
  --dataset OUT/inputs.jsonl \
  --model <MODEL> --api-key DEEPSEEK_API_KEY \
  --concurrency 10 > OUT/baseline_predictions.jsonl
```

Then score and compute metrics (gold is merged from the original dataset):

```bash
python $SKILL/scripts/run_prompt_optimizer.py score-predictions \
  --task-type <T> --predictions OUT/baseline_predictions.jsonl \
  --dataset <dataset_path> > OUT/baseline_results.jsonl

python $SKILL/scripts/run_prompt_optimizer.py compute-metrics \
  --task-type <T> --results OUT/baseline_results.jsonl > OUT/baseline_metrics.json
```

Record `baseline_correct_ids` (ids where `is_correct` is true) — guardrails compare every candidate against this fixed baseline. If there are no wrong cases, write `final_prompt.md` = current prompt and finish.

### Iteration — repeat up to `rounds` times, each into `OUT/round_{N}/`

Each round operates on the **current best prompt**. Re-infer it over the dataset via `run-inference` and score, to get this round's wrong cases. If none, record the round and continue.

1. **Attribution + gradients (agent)** — read `assets/prompts/badcase_attribution.md`; analyze each wrong case's root cause and aggregate systematic causes into gradients. Write `round_{N}/wrong_cases_attributed.jsonl` and `round_{N}/gradients.jsonl`. No gradients → record round, continue.
2. **Rewrite suggestions (agent)** — read `assets/prompts/rewrite_suggestion.md`; turn each gradient into a minimal, single-action edit. Write `round_{N}/rewrite_suggestions.jsonl`.
3. **Strategy grouping (agent)** — read `assets/prompts/strategy_grouping.md`; group suggestions into ≤4 single-direction strategies. Write `round_{N}/strategy_groups.json`.
4. **Candidate generation (agent)** — read `assets/prompts/candidate_generation.md`; for each strategy group, apply its suggestions to the current prompt and produce a candidate. Always also include a `hold` candidate = the unchanged current prompt. Write each to `round_{N}/candidates/{candidate_id}.md`.
5. **Score every candidate (llm_api → python_cli)** — for each candidate:

```bash
python $SKILL/scripts/run_prompt_optimizer.py run-inference \
  --prompt round_{N}/candidates/{candidate_id}.md \
  --dataset OUT/inputs.jsonl \
  --model <MODEL> --api-key DEEPSEEK_API_KEY --concurrency 10 > round_{N}/candidates/{id}_preds.jsonl

python $SKILL/scripts/run_prompt_optimizer.py score-predictions \
  --task-type <T> --predictions round_{N}/candidates/{id}_preds.jsonl \
  --dataset <dataset_path> > round_{N}/candidates/{id}_results.jsonl

python $SKILL/scripts/run_prompt_optimizer.py compute-metrics \
  --task-type <T> --results round_{N}/candidates/{id}_results.jsonl
```

6. **Guardrail check (python_cli)** — for each candidate build the payload and run:

```bash
python $SKILL/scripts/run_prompt_optimizer.py check-guardrails --payload round_{N}/candidates/{id}_guardrail.json
```

**Noise floor (do this when the target model is sampled, i.e. temperature > 0 — the common case).** Re-running the *unchanged* prompt flips some previously-correct rows purely by chance; on a small eval set that jitter alone can exceed `max_correct_to_wrong_rate` and wrongly disqualify every candidate — including `hold`. So take the `hold` candidate's own `correct_to_wrong_rate` (from its guardrail result — `hold` is the unchanged prompt re-inferred) and pass it as `noise_floor_rate` in **every** candidate's payload this round. The check then judges regressions *above the measured noise*: effective threshold = `max_correct_to_wrong_rate + noise_floor_rate`. If `hold`'s rate is 0 (deterministic model), this is a no-op.

Payload shape:
```json
{
  "candidate_metrics": {...},
  "baseline_metrics": {...},
  "baseline_correct_ids": ["1","3"],
  "candidate_results": [{"id":"1","is_correct":true}, ...],
  "noise_floor_rate": 0.06,
  "eval_plan": { "primary_metric": "...", "secondary_metrics": [...], "guardrails": {...} }
}
```

7. **Select (agent)** — among `eligible` candidates pick the one with the best `primary_metric`; it becomes the next round's current prompt. Update the global best if it beats the global best primary value. Write `round_{N}/candidate_scores.json` and append to `OUT/round_history.jsonl`.

### Final validation on HOLDOUT (llm_api → python_cli) → `OUT/holdout_metrics.json`

The whole point of the split: the global-best prompt was chosen by its TRAIN score, which is optimistic. Measure it **once** on `HOLDOUT` — data the loop never saw — to get the number you can actually trust. Also re-score the *original baseline* prompt on `HOLDOUT` so the comparison is apples-to-apples on the same unseen rows:

```bash
# strip gold, then infer + score both the final prompt and the original baseline on HOLDOUT
python $SKILL/scripts/run_prompt_optimizer.py load-dataset --dataset HOLDOUT --strip-gold > OUT/holdout_inputs.jsonl
for P in final_prompt baseline_prompt; do
  python $SKILL/scripts/run_prompt_optimizer.py run-inference --prompt OUT/$P.md \
    --dataset OUT/holdout_inputs.jsonl --model <MODEL> --api-key DEEPSEEK_API_KEY --concurrency 10 > OUT/${P}_holdout_preds.jsonl
  python $SKILL/scripts/run_prompt_optimizer.py score-predictions --task-type <T> \
    --predictions OUT/${P}_holdout_preds.jsonl --dataset HOLDOUT > OUT/${P}_holdout_results.jsonl
  python $SKILL/scripts/run_prompt_optimizer.py compute-metrics --task-type <T> \
    --results OUT/${P}_holdout_results.jsonl
done
```

Write `OUT/holdout_metrics.json` with both prompts' holdout metrics. Compute the **generalization gap** = TRAIN-best primary − HOLDOUT primary of the final prompt. A small gap means the gain is real; a large gap means the loop overfit the train set and you should say so plainly rather than report the rosy train number.

### Final (agent) — report + final prompt → `OUT/best_round_report.md`, `OUT/final_prompt.md`

Write the global-best prompt to `OUT/final_prompt.md`. Read `assets/prompts/best_round_report.md` and write a human-readable rationale to `OUT/best_round_report.md`. Lead the report with the **HOLDOUT** movement (baseline → final on held-out data), not the train number — that is the trustworthy result. State the generalization gap. All numbers must come from real artifacts. Do not claim "production safe" unless the holdout gain is meaningful and guardrails passed (accounting for the noise floor).

## Degradation

CLI exit codes (every subcommand follows this contract):

- `0` — success, continue.
- `2` — input/boundary error (invalid dataset, missing/unresolvable `--api-key`, bad args). Stop and ask the user to fix the input; do not retry.
- `1` — unexpected runtime failure (e.g. every row in `run-inference` errored). Report the command and stderr to the user.

Step-level degradation:

- `validate-inputs` invalid → stop, report to user (exit-2 boundary).
- An LLM step yields nothing usable (no gradients / no suggestions / no strategies) → record the round and keep the current prompt; do not fabricate.
- A single candidate generation fails → skip that group, continue others.
- Report step fails → emit a minimal numeric summary from the metrics artifacts.

## Artifact Reading Order

1. `eval_plan.json` — task type, metrics, guardrails.
2. `baseline_results.jsonl` / `baseline_metrics.json` — baseline errors and scores.
3. `round_{N}/wrong_cases_attributed.jsonl`, `gradients.jsonl`, `rewrite_suggestions.jsonl`, `strategy_groups.json` — the optimization chain.
4. `round_{N}/candidate_scores.json` — candidate metrics, guardrail results, selection.
5. `round_history.jsonl` — round-by-round advancement.
6. `holdout_metrics.json` — final & baseline prompt scored on held-out data; the trustworthy number + generalization gap.
7. `best_round_report.md` — human-readable rationale.
8. `final_prompt.md` — the prompt to hand off.

When you report back to the user, lead with the **holdout** primary-metric movement (baseline → final on held-out data) and the generalization gap, then the final prompt path, the strategy evidence behind the selected round, and any guardrail or limitation noted in the report. The train-set number is a means, not the result.

## Dataset Formats

JSONL rows: `{"id":"s1","input":"客户要求退款","gold":"after_sales"}`. CSV/Excel columns are auto-detected. Input columns: `input, text, query, utterance, 样本, 输入, 文本, 用户输入`. Gold columns: `gold, label, labels, answer, expected, 正确答案, 标注, 标签`. On ambiguity, pass `--input-column` / `--gold-column`.
