#!/usr/bin/env python3
"""PreToolUse hook: block Write/Edit if content contains hardcoded secrets."""

import json
import os
import re
import sys

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub Server Token"),
    (r"github_pat_[a-zA-Z0-9_]{20,}", "GitHub Fine-grained PAT"),
    (r"password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password"),
    (r"secret\s*=\s*[\"'][^\"']+[\"']", "Hardcoded secret"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "Private Key"),
]

SKIP_PATTERNS = [
    r"\.env\.example$",
    r"\.md$",
    r"(?:^|/)test_[^/]*\.py$",
    r"(?:^|/)tests?/",
]


def should_skip(filepath: str) -> bool:
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, filepath):
            return True
    return False


def scan_content(content: str) -> list[str]:
    findings = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, content):
            findings.append(label)
    return findings


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Write", "Edit"):
        return

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")

    if not filepath or should_skip(filepath):
        return

    content = ""
    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "")

    if not content:
        return

    findings = scan_content(content)
    if findings:
        matched = ", ".join(findings)
        print(json.dumps({
            "decision": "block",
            "reason": f"Potential secret(s) detected: {matched}. "
                      f"Use environment variables instead of hardcoding secrets.",
        }))


if __name__ == "__main__":
    main()
