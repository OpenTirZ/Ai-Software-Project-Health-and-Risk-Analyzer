"""V2 LangGraph pipeline for AI Software Project Health & Risk Analyzer.

Input contract
--------------
- contributors: list[MongoDB contributor documents] or {"contributors": [...]}
- commits: list[MongoDB commit documents] or {"commits": [...]}

Run locally
------------
pip install langgraph langchain-openai langchain-core python-dotenv
export OPENROUTER_API_KEY="your_openrouter_api_key"
python pipeline.py

For FastAPI integration
-----------------------
from pipeline import run_analysis
report = run_analysis(contributors_json, commits_json)

The health score is a transparent, rule-based indicator, not a trained ML
prediction. V2 only assesses information present in contributor and commit
records. Issues, pull requests/reviews and sprint data are not inferred.
"""
