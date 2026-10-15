"""Rubric reward for GRPO training with ms-swift.

Load with ``swift rlhf --external_plugins train/rl/rubric_reward.py
--reward_funcs rubric_reward``. Each completion is graded in one request to an
OpenAI-compatible judge, which returns hit/miss verdicts for the record's
rubrics. The reward is the fraction of rubrics hit.

The final answer (thinking removed) is limited to 1024 tokens of the policy
tokenizer. Longer answers are truncated before judging and receive a -1.0
penalty. Failed or unparsable judgments score 0.0, plus the same penalty.

Environment variables:
  JUDGE_BASE_URL    judge endpoint (default http://127.0.0.1:8001/v1)
  JUDGE_MODEL       served judge model name (default judge)
  JUDGE_API_KEY     optional bearer token
  REWARD_TOKENIZER  tokenizer for the length limit (default Qwen/Qwen3-8B)
"""

import asyncio
import json
import os
import re
from typing import List

import aiohttp
from transformers import AutoTokenizer

from swift.rewards import AsyncORM, orms

MAX_ANSWER_TOKENS = 1024
LENGTH_PENALTY = -1.0
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 4096
JUDGE_CONCURRENCY = 32
JUDGE_TIMEOUT = 300

JUDGE_SYSTEM_PROMPT = """\
You are a strict but fair evaluator of research proposals. You need to evaluate if the Proposed Research Plan satisfies the provided evaluation rubrics.

## Rules
1. Evaluate each rubric independently.
2. Be strict but reasonable — semantic equivalence counts.
3. Focus on substance, not style.
4. Only score based on what is explicitly stated.
5. Be skeptical, careful, and come up with valid criticisms. Be as strict as possible, while being unbiased and reasonable.
6. Note that the plan should not just say it satisfies these desiderata, don't be fooled by that. Check carefully WHETHER, HOW and WHY the proposed plan meets each desiderata for this rubric item one by one.

## Output Format
Return ONLY a JSON object. For each rubric, give a hit (1) or miss (0) and a brief reason. Then give the total.

Example with 3 rubrics:
```json
{
  "rubrics": [
    {"id": 1, "reason": "Proposal clearly identifies X.", "hit": 1},
    {"id": 2, "reason": "No mention of Y.", "hit": 0},
    {"id": 3, "reason": "Method addresses Z.", "hit": 1}
  ],
  "total_score": 2,
  "max_score": 3
}
```

Do NOT output anything outside the JSON object. No markdown, no explanation before or after."""


def strip_thinking(text):
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()


def build_user_prompt(completion, rubrics):
    criteria = "\n".join(f"- Rubric {r['id']} ({r['category']}): {r['criterion']}" for r in rubrics)
    return f"## Proposal\n\n{completion.strip()}\n\n## Rubrics\n\n{criteria}\n\nEvaluate each rubric and return the JSON."


def extract_json(response):
    text = strip_thinking(response)
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    brace = re.search(r"\{[\s\S]*\}", text)
    if not brace:
        return {}
    try:
        return json.loads(brace.group(0))
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", brace.group(0)))
        except json.JSONDecodeError:
            return {}


def parse_score(result):
    """Use the judge's total/max when given, otherwise the fraction of hits."""
    if "total_score" in result and "max_score" in result:
        maximum = result["max_score"]
        return result["total_score"] / maximum if maximum > 0 else 0.0
    hits = [r.get("hit", 0) for r in result.get("rubrics", [])]
    return sum(hits) / len(hits) if hits else 0.0


class RubricReward(AsyncORM):

    def __init__(self, args=None, **kwargs):
        super().__init__(args, **kwargs)
        self.url = os.environ.get("JUDGE_BASE_URL", "http://127.0.0.1:8001/v1").rstrip("/") + "/chat/completions"
        self.model = os.environ.get("JUDGE_MODEL", "judge")
        self.headers = {"Content-Type": "application/json"}
        if os.environ.get("JUDGE_API_KEY"):
            self.headers["Authorization"] = f"Bearer {os.environ['JUDGE_API_KEY']}"
        self.tokenizer = AutoTokenizer.from_pretrained(os.environ.get("REWARD_TOKENIZER", "Qwen/Qwen3-8B"),
                                                       trust_remote_code=True)

    def truncate(self, text):
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= MAX_ANSWER_TOKENS:
            return text, 0.0
        return self.tokenizer.decode(ids[:MAX_ANSWER_TOKENS], skip_special_tokens=False), LENGTH_PENALTY

    async def judge(self, session, semaphore, completion, rubrics):
        payload = {
            "model": self.model, "temperature": JUDGE_TEMPERATURE, "max_tokens": JUDGE_MAX_TOKENS,
            "messages": [{"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                         {"role": "user", "content": build_user_prompt(completion, rubrics)}],
        }
        async with semaphore:
            # Retry once with thinking disabled if the first attempt fails.
            for request in [payload, dict(payload, chat_template_kwargs={"enable_thinking": False})]:
                try:
                    async with session.post(self.url, headers=self.headers, json=request,
                                            timeout=aiohttp.ClientTimeout(total=JUDGE_TIMEOUT)) as resp:
                        if resp.status != 200:
                            delay = int(resp.headers.get("Retry-After", 5)) if resp.status == 429 else 2
                            await asyncio.sleep(delay)
                            continue
                        data = await resp.json()
                    result = extract_json(data["choices"][0]["message"]["content"] or "")
                    if result:
                        return parse_score(result)
                except Exception as exc:
                    print(f"[rubric_reward] judge request failed: {type(exc).__name__}: {exc}")
        return None

    async def __call__(self, completions, rubrics, **kwargs) -> List[float]:
        rubrics = [json.loads(r) if isinstance(r, str) else r for r in rubrics]
        answers, penalties = zip(*(self.truncate(strip_thinking(c)) for c in completions))
        semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)
        async with aiohttp.ClientSession() as session:
            scores = await asyncio.gather(*[self.judge(session, semaphore, a, r)
                                            for a, r in zip(answers, rubrics)])
        failed = sum(s is None for s in scores)
        if failed:
            print(f"[rubric_reward] {failed}/{len(scores)} judgments failed and scored 0")
        return [(s or 0.0) + p for s, p in zip(scores, penalties)]


orms["rubric_reward"] = RubricReward
