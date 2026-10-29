
# A Controlled Evaluation of LLM Agents with Direct Context, Tool Use, and Persistent Memory

This project is a controlled empirical evaluation of one local LLM agent under three information-access conditions:

1. **Direct context** — the task's relevant information is placed directly in the agent's prompt.
2. **Tool retrieval** — the same information is stored in a fixed knowledge base and must be retrieved through tools.
3. **Persistent memory** — the same information is stored in a persistent note store and must be retrieved through memory.

The LLM, benchmark tasks, gold answers, and relevant information are held constant as far as the experimental design allows. The independent variable is the **information-access mechanism**.

This is intentionally narrower than an adaptive agent architecture. The project does not claim to evaluate adaptive planning or self-correction as separate capabilities.

## Benchmark is model-agnostic

The benchmark is designed to be independent of the specific LLM used. The reference FYP experiment uses `qwen2.5:3b` so that the model remains fixed while the information-access mechanism is varied. This isolates the effect of direct context, tool retrieval, and persistent memory.

Researchers can substitute another locally available instruction-following LLM through the Ollama model setting and run the same benchmark without changing the task definitions or grading rules. For example, the same benchmark can be evaluated with Qwen, Llama, Mistral, Gemma, or another compatible local model.

This creates two distinct uses of the project:

1. **Primary FYP experiment:** one fixed model, `qwen2.5:3b`, compared across the three access conditions.
2. **Model-comparison use:** the same benchmark can later be run across multiple LLMs to study whether the observed access-mechanism effects are consistent across models.

Model comparison is not part of the primary causal claim of this FYP. If multiple models are evaluated, model identity becomes an additional experimental variable and should be analyzed separately.

## Research question

> How do direct contextual access, external tool retrieval, and persistent memory affect the performance and efficiency of the same local LLM agent?

## What changed from the earlier version

The old benchmark often made the answer unavailable to two conditions and available only to the intended condition. That measured information availability, not the effect of the access mechanism. The new benchmark gives every condition access to the same underlying information through a different channel.

The old `expected_pass` field is therefore removed. A task can pass or fail independently in every condition, and the grader does not assume which condition should win.

## Experimental setup

The reference experiment uses `qwen2.5:3b` through Ollama. No paid API or cloud service is required. Keep this model fixed when reproducing the primary FYP experiment.

The synthetic knowledge base is used to make the experiment reproducible. It contains paper findings and review facts. The same underlying content is represented in the direct-context payload and memory payload, while the tool condition retrieves it from the knowledge base.

Each task contains:

- one semantic task prompt;
- the gold answer rule;
- expected successful tool calls for the tool/memory retrieval path;
- a direct-context representation of the same information;
- a memory representation of the same information.

## Metrics

Primary metric:

- **Task success rate** — percentage of benchmark tasks passed by the deterministic grader.

Secondary metrics:

- average turns per task;
- average latency;
- average total tokens;
- number of executed tool calls;
- rejected/invalid tool calls;
- per-task success/failure pattern.

These let the study ask not only whether an access mechanism works, but whether it changes the cost of solving the same task.

## Project structure

```text
fyp-agent-eval-v2/
├── README.md
├── requirements.txt
├── .env.example
├── Open Dashboard.bat
├── data/
│   ├── knowledge.json
│   ├── papers.json
│   ├── facts.json
│   └── tasks_seed.json
├── src/
│   ├── agent.py
│   ├── grader.py
│   ├── llm_client.py
│   ├── memory_store.py
│   ├── run_eval.py
│   ├── dashboard.py
│   ├── test_harness.py
│   └── tools.py
└── results/
```

## Setup on Windows

Open PowerShell in the project root folder — the folder containing `README.md` and `requirements.txt`.

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure it if needed.

Make sure Ollama is running and the model is available:

```powershell
ollama list
ollama pull qwen2.5:3b
```

You only need to pull the model once. If PowerShell blocks virtual-environment activation, you can use the Python executable inside `.venv` directly or adjust your PowerShell execution policy according to your environment.

## Run deterministic checks first

From the project root:

```powershell
python src\test_harness.py
```

This does not call the LLM. It verifies the benchmark data, access gates, memory retrieval, agent execution semantics, and grader.

## Run the benchmark from the terminal

From the project root:

```powershell
python src\run_eval.py
```

Run one task:

```powershell
python src\run_eval.py --task K-01
```

Run selected tasks:

```powershell
python src\run_eval.py --task K-01 K-05 K-08
```

Run one condition only:

```powershell
python src\run_eval.py --condition memory
```

A JSON report is written to the project's `results/` folder.

## Run the GUI dashboard

The project includes a local browser-based dashboard called **Agent Lab**. It lets you view saved evaluation reports, compare the baseline/tool/memory conditions, inspect task-level answers and retrieval results, and start a new full evaluation from the page.

The dashboard uses Python's standard library and does not require additional GUI packages or cloud services. Running evaluations still requires the project's dependencies and a working local Ollama model.

### Option 1: Launch with the Windows batch file

1. Make sure Ollama is running and `qwen2.5:3b` is available.
2. Open the project root folder — the folder containing `README.md` and `Open Dashboard.bat`.
3. Double-click **`Open Dashboard.bat`**.
4. Your browser should open the dashboard at:

   `http://127.0.0.1:8765`

5. Select an existing report to inspect previous results, or use **Run full evaluation** to run the benchmark again.

Keep the terminal window open while using the dashboard. Closing it or pressing `Ctrl+C` stops the dashboard server.

### Option 2: Launch from PowerShell

Open PowerShell in the project root and run:

```powershell
.venv\Scripts\Activate.ps1
python src\dashboard.py
```

Then open `http://127.0.0.1:8765` in your browser if it does not open automatically.

If you have not created the virtual environment yet, complete the Windows setup steps first.

### Using the dashboard

- **Saved reports:** Choose a report to inspect the results from an earlier evaluation.
- **Run full evaluation:** Starts a new evaluation across the three conditions. The dashboard displays output and loads the new report when the run finishes.
- **Refresh:** Reloads the available reports and selected report data.
- **Stop the dashboard:** Close its terminal window or press `Ctrl+C` in that window.

The dashboard is intended for local use on your own computer and binds to `127.0.0.1`. It does not require a cloud service.

A new evaluation creates another timestamped JSON report in `results/`. Existing reports should be preserved, especially the report used for the final research results.

## Important methodological rule

Do not add a task where the answer is deliberately absent from two conditions. If a new task is added, the same underlying answer information must be represented in all three conditions:

- direct context for baseline;
- retrievable knowledge for tools;
- retrievable persistent note for memory.

The difference should be **how the agent gets the information**, not whether it exists.

## Interpretation

A result such as:

```text
baseline: 10/12
   tool:  8/12
 memory: 11/12
```

does not automatically prove that memory is better. It is evidence that, under this benchmark and model, the three access mechanisms produced different outcomes. The paper should analyze the task-level failure patterns and efficiency metrics before drawing conclusions.

## Limitations

The benchmark uses synthetic knowledge and the primary study uses a single local model. The current FYP therefore measures behavior in a controlled environment rather than claiming general superiority of one mechanism across all LLMs or real-world agents.

The benchmark itself is model-agnostic, so additional models can be evaluated later. Such experiments should be reported separately from the primary fixed-model comparison because changing the LLM introduces another independent variable.

A later version can add more models, more domains, repeated runs with different random seeds, or a larger benchmark. Those are extensions, not requirements for the core experiment.
