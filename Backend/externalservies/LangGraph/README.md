# Project Health Analyzer — V1

## Overview
V1 analyzes GitHub contributors and commits with LangGraph and returns a JSON project-health report.

## Inputs
- `contributors`: contributor records from GitHub/MongoDB
- `commits`: commit records from GitHub/MongoDB

## Workflow
1. Validate and normalize input
2. Analyze contributors
3. Analyze commits
4. Calculate project-health score and risks
5. Generate AI insights
6. Build the final JSON report

## Output
The report includes project health, contributor analysis, commit analysis, an executive summary, recommendations, and limitations.

<!-- ## Run locally
```bash
pip install langgraph langchain-openai langchain-core python-dotenv
export OPENROUTER_API_KEY="your_api_key"
python langgraph_project_health_pipeline.py
``` -->

The script includes dummy data for testing. Set `OPENROUTER_MODEL` to choose a chat model.

## V1 limitations
The health score is a heuristic based on contributor and commit data; it is not a trained prediction. Issue, pull-request, review, and sprint risks are not assessed because those inputs are not included.
