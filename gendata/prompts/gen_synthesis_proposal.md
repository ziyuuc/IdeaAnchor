You are an expert research analyst and proposal writer. Your task is to produce TWO things given a set of prior works (with their abstracts), the core idea of a paper, and the original paper content:

1. A **synthesis narrative** that reconstructs the reasoning process from prior works to the new idea
2. A **research proposal** that presents the motivation and method

## Input You Receive

1. **Core idea** extracted from the paper (innovation, departure, key insight)
2. **Prior works** with their roles, cite_ids, what was learned, and abstracts
3. **Original paper** for technical detail reference

---

## Part 1: Synthesis Narrative (400-600 words)

Write this narrative **in the first person, as the researcher who wrote this paper**. You are reconstructing their reasoning process — how they analyzed these prior works, identified gaps and opportunities, and synthesized a new approach.

### cite_id Convention

Reference each prior work using its `@cite_id` (e.g., "@chen2020simclr"). ONLY mention papers that appear in the provided prior_works list. Do not reference papers outside the list.

### CRITICAL RULES:
- This is a **structured record of analytical reasoning** — how specific observations about prior work led to specific design decisions.
- Prioritize **clarity and depth of reasoning** over narrative polish. The goal is to make the logical chain from prior work to new idea explicit and traceable.
- Use precise, direct analytical language. Avoid dramatic or emotional expressions (e.g., "it struck me", "I kept running into a wall", "the turning point", "this idea stuck with me"). Simply state what was observed and why it matters.
- The narrative consists of exactly **three paragraphs**, separated by blank lines. Do NOT include phase labels or headers (no "Phase 1:", "Phase 2:", etc.) — just write the three paragraphs directly.

### Structure (three paragraphs):

**Paragraph 1 — Analysis of individual prior works (~100-150 words):**
Analyze each key prior work individually. For each paper, state: (a) what it concretely achieved or proposed, (b) what technical limitation, gap, or opportunity it exposes, and (c) why that observation matters for the current research direction. Cover all or most of the prior works in this paragraph. Each paper should get its own focused analysis rather than being lumped together with others.

**Paragraph 2 — Cross-paper synthesis (~200-250 words):**
This paragraph should contain NO new per-paper analysis — instead, focus entirely on how the observations from Paragraph 1 logically connect to form a new approach. This is the most important paragraph. Make the reasoning chain explicit:
- Which specific idea from one paper directly addresses a limitation identified in another?
- What new possibility emerges when techniques from different works are combined?
- Why had this particular combination not been explored before?
- What is the concrete mechanism by which the combined approach works?

**Paragraph 3 — Problem and approach summary (~200-250 words):**
Distill the reasoning into two clear points: (1) The research problem: identifying the specific gaps or limitations revealed by prior work, analyzing their underlying causes, and defining the precise research questions the proposed approach aims to address; (2) The proposed approach at a high level — what the core idea is, which insights from the above analysis it draws on, and why this design is expected to work. This paragraph should be a concise crystallization, not a repetition of Paragraph 2.

---

## Part 2: Research Proposal

The proposal has exactly **two sections**. Follow this format precisely:

### Section 1: Research Motivation & Problem Definition

Write 2-3 paragraphs that:
- Define the specific research problem being addressed
- Identify the concrete gap or limitation in existing approaches, citing which prior works (`@cite_id`) reveal this gap
- Explain why this gap matters and what opportunity it creates
- Be specific and technical — avoid vague statements like "existing methods have limitations"

### Section 2: Core Idea & Methodology

This section consists of an overview paragraph followed immediately by a numbered component list. Do NOT include sub-headers like "Part A", "Part B", "Overview:", or "Method Components:". Just write the content directly.

**Overview paragraph (first paragraph of this section):**
A concise high-level description of the proposed approach. State the core idea in 2-3 sentences, then briefly explain why this formulation addresses the identified gap.

**Numbered method components (immediately after the overview paragraph):**
Break the method into its key technical components. Each component follows this exact format:

```
1. **[Component Name]**: [Description of what this component does, why it is needed, and how it draws from or extends prior work. Reference relevant @cite_id.]

2. **[Component Name]**: [Description...]
```

Rules for method components:
- Use a numbered list (1, 2, 3, ...) with bold component names
- Each component should be 2-4 sentences
- Each component must explain: (a) what it does, (b) why it is needed, (c) how it relates to or extends prior work
- Reference prior works using `@cite_id` where appropriate — most components should cite at least one prior work
- Typically 3-5 components depending on the method's complexity. Focus on the core technical components, not auxiliary details like training tricks.

After the numbered list, add 1-2 sentences explaining why these components work together as a coherent system.

---

## Writing Guidelines

- Use `@cite_id` to reference prior works throughout. Only reference papers from the provided prior_works list.
- Integrate `@cite_id` references naturally into sentences (e.g., "Building on @radford2021clip, we..." or "...as shown by @tancik2020fourier"). Avoid dangling citations at the end of clauses.
- Be technically precise. Include specific design choices drawn from the paper.
- Write the proposal in a propositional tone ("We propose...", "Our approach...") rather than retrospective ("We found that...").
- The proposal should read as a self-contained research plan.
- Keep the proposal to approximately 400-600 words.
- Do NOT include a title, abstract, conclusion, or any sub-headers/labels within the two sections.

## Output Format (JSON):

```json
{
  "synthesis_narrative": "Three-paragraph first-person narrative as described above. Use @cite_id to reference papers. No phase labels or headers.",
  "motivation": "Section 1 content (Research Motivation & Problem Definition). Use \\n\\n for paragraph breaks.",
  "method": "Section 2 content (Core Idea & Methodology). Include both the overview paragraph and the numbered component list."
}
```
