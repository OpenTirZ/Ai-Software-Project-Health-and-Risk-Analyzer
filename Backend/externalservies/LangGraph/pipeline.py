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


from __future__ import annotations

import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # .env support is optional
    pass


PIPELINE_VERSION = "2.0.0"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# This is a chat/generation model. Do not use an embedding-only model here.
DEFAULT_CHAT_MODEL = "nvidia/nemotron-3.5-super-vl:free"
MAX_RECENT_COMMITS = 10
MAX_PROMPT_TOP_CONTRIBUTORS = 8
MAX_PROMPT_RECENT_COMMITS = 5
MAX_COMMIT_MESSAGE_LENGTH = 300

NOT_ASSESSED = [
    "Issue age, stale issues and issue-resolution time (issue records were not supplied).",
    "Pull-request backlog, review latency and merge bottlenecks (PR/review records were not supplied).",
    "Sprint completion, milestone slippage and schedule risk (sprint/milestone records were not supplied).",
    "Code correctness, maintainability, bugs and test coverage (source diffs and test results were not supplied).",
]
