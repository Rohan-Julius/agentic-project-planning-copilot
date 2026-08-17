"""Day 21 retrieval evaluation driver (spec §24.9). Not marked slow — no live LLM calls,
pure embedding + vector search, should complete in well under a minute.
"""
from __future__ import annotations

from evaluation.scripts import run_retrieval_evaluation


def test_run_day21_retrieval_evaluation(client):
    results = run_retrieval_evaluation.main(client)
    assert len(results) >= 30
    for r in results:
        if not r["expect_no_answer"]:
            assert r["correct_source_found"] in (True, None)
