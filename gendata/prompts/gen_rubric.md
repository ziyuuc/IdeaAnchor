You are an expert in designing evaluation criteria for research proposals. Your task is to generate a set of **rubric items** that can be used to score the quality of a research proposal generated from a given set of prior works.

## Context

You are given:
1. **Prior works** — a set of papers with their roles (Direct Predecessor, Gap & Motivation, Inspiration Source, Methodological Foundation), cite_ids, and what was learned from each
2. **Synthesis narrative** — a reasoning process showing how insights from the prior works connect
3. **Reference proposal** — a ground-truth proposal (motivation + method) derived from these prior works, which serves as ONE valid example but NOT the only valid answer

The rubrics you generate will be used in reinforcement learning to score model-generated proposals. The model receives the same set of prior works (titles + abstracts) and must produce a research proposal with motivation and method.

## Critical Design Principles

**1. Ground rubrics in the prior works, not in the specific reference proposal.**
Rubrics should check whether the proposal meaningfully engages with the gaps, limitations, and opportunities revealed by the prior works. They should NOT check whether the proposal reproduces the exact method from the reference proposal.

**2. Allow multiple valid solutions.**
This is the most important principle. The same set of prior works can inspire different research problems and different methods. Your rubrics should admit multiple high-scoring proposals. A proposal with a completely different method than the reference can still score full marks if it is well-reasoned and grounded.

**3. Motivation rubrics can be moderately specific; method rubrics must be high-level.**
- Motivation rubrics: It is reasonable to check that the proposal identifies specific gaps or limitations that the prior works clearly reveal. These are somewhat constrained by the input papers.
- Method rubrics: These should check for general properties (e.g., "addresses the encoding challenge", "leverages cross-modal alignment") rather than specific techniques (e.g., "uses Fourier features", "uses contrastive loss"). A method rubric should be satisfiable by multiple different technical approaches.

**4. Each rubric must be independently evaluable as pass/fail.**
A reward model will check each rubric against the generated proposal. The rubric must be clear enough that pass/fail can be determined from reading the proposal alone (given knowledge of the prior works).

## Rubric Categories

Generate rubrics from these categories:

### Motivation Rubrics (2-3 items)
These check whether the proposal correctly identifies research problems and gaps grounded in the prior works.
- Does it identify the core limitation or gap that the "Gap & Motivation" papers reveal?
- Does it explain why this gap matters (what practical or theoretical consequence it has)?
- Does it articulate what opportunity the combination of prior works creates?

### Method Rubrics (2-3 items)
These check high-level properties of the proposed approach. Frame them as "what the method should achieve or address" rather than "what specific technique it should use."
- Does the method address the identified gap in a principled way?
- Does it draw on or extend ideas from the provided prior works?
- Does it handle specific technical challenges that the prior works surface (e.g., encoding challenges, scalability issues, representation problems)?
- Are the method components coherent and mutually supportive?

### Overall Quality Rubrics (1-2 items)
- Is the proposal internally consistent (motivation leads to method)?
- Does the proposal present a feasible and complete research plan?

## Output Format

Generate 5-7 rubric items total. Each rubric is a JSON object with:
- `id`: integer (1, 2, 3, ...)
- `category`: one of "motivation", "method", "overall"
- `criterion`: a single, clear sentence describing what the proposal must demonstrate to earn this point. Use `@cite_id` to reference specific prior works where appropriate.

```json
{
  "rubrics": [
    {
      "id": 1,
      "category": "motivation",
      "criterion": "The proposal should identify that [specific gap/limitation] as revealed by [prior works]."
    },
    ...
  ]
}
```

## Writing Guidelines for Individual Rubrics

- Each criterion is ONE sentence. Be precise but not overlong.
- For motivation rubrics: reference which prior work(s) reveal the gap using `@cite_id`.
- For method rubrics: describe what the method should *achieve* or *address*, not what specific technique it should use. For example:
  - GOOD: "The method should address the challenge of encoding low-dimensional spatial inputs into representations rich enough for fine-grained discrimination."
  - BAD: "The method should use Random Fourier Features to encode GPS coordinates."
  - GOOD: "The method should incorporate a mechanism for aligning visual features with location representations in a shared space."
  - BAD: "The method should use CLIP-style contrastive learning to align images with GPS embeddings."
- Avoid rubrics that can only be satisfied by one specific approach. If you find yourself describing a concrete technique, abstract it one level.
- Make sure the full set of rubrics, taken together, does NOT uniquely determine a single method. Test this mentally: could a different but equally valid approach pass all rubrics?