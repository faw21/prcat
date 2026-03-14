"""Integration tests with real LLM API calls."""
from __future__ import annotations

import os
import pytest
from dotenv import load_dotenv

load_dotenv("/Users/aaronwu/Local/my-projects/give-it-all/.env", override=True)


ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@pytest.mark.skipif(not ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY not set")
def test_real_review_claude():
    """Integration test: real Claude API call with a simple PR diff."""
    from prcat.fetcher import PRData
    from prcat.reviewer import review_pr

    # Small diff to minimize cost
    small_diff = """\
diff --git a/utils.py b/utils.py
index abc123..def456 100644
--- a/utils.py
+++ b/utils.py
@@ -1,5 +1,8 @@
 def add(a, b):
-    return a + b
+    \"\"\"Add two numbers.\"\"\"
+    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
+        raise TypeError("Expected numbers")
+    return a + b
"""
    pr = PRData(
        number=1,
        title="Add type check to add()",
        author="testuser",
        base_branch="main",
        head_branch="feat/type-check",
        body="Adds runtime type validation.",
        state="open",
        diff=small_diff,
        files_changed=["utils.py"],
        additions=4,
        deletions=1,
        comments=[],
        repo="test/repo",
        url="https://github.com/test/repo/pull/1",
    )

    result = review_pr(pr, provider="claude", model="claude-haiku-4-5")

    assert result.pr_number == 1
    assert isinstance(result.raw_text, str)
    assert len(result.raw_text) > 20
    assert result.verdict in ("lgtm", "needs-minor-changes", "needs-major-changes", "reviewed")
    print(f"\nVerdict: {result.verdict}\nReview:\n{result.raw_text[:300]}...")
