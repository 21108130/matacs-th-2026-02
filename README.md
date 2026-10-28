# MATACS-TH-2026-02: AI-Assisted Proposal Triage Design

**Candidate:** Maira Javed
**Reference:** MATACS-TH-2026-02
**Time spent:** 1 hour
## Overview

This repository provides an AI-driven process for sorting out contractors' bids for a commercial solar project installation. AI is leveraged to extract structured facts from unstructured text of the proposals in question, supported by evidence. Deterministic logic verifies these facts and uses versioned criteria for scoring and sorting only verified proposals. A human makes the award decision.

The optional offline prototype showcases the deterministic stage of scoring and sorting using hand-curated facts for the hypothetical proposals A-E. It does **not** parse any PDFs, run an AI model, or validate any real-world credentials. The extraction prompt from `PROMPTS.md` is an example of the integration prompt, not an offline prototype prompt.

## Repository contents

- [Process flow diagram](diagram/flow.png)
- [Design write-up](WRITEUP.md)
- [Extraction prompt and validation contract](PROMPTS.md)
- [Expected output for proposals A–E](ranking.json)
- [Editable criteria and scoring configuration](prototype/criteria.json)
- [Curated fixture facts](prototype/sample_facts.json)
- [Deterministic scoring script](prototype/score.py)
- [Detailed score breakdown and review flags](prototype/score_details.json)
- [Prototype guide](prototype/README.md)
- [Prototype tests](prototype/tests/test_score.py)

## Run the prototype

Requires Python 3.10 or newer. It uses only the Python standard library.

From the repository root:

```bash
python prototype/score.py
python -m unittest discover -s prototype/tests -p "test_*.py"
```

It verifies the weights set up, analyzes mandatory requirements and hard constraints, computes points per criterion, sorts only those proposals which have been validated, and generates the five required fields in `ranking.json`. Detailed scores and flags are separately recorded in `prototype/score_details.json`. Running this script for the same configuration and fixture again will yield the same output.

For experimenting with a different rubric, change `prototype/criteria.json`. The sum of weights needs to be 100. These formulas along with their normalization anchors are only examples of policies, not those provided in the assessment prompt.

## Design Choices

1. Criteria, mandatory tests, scoring weights, and normalizations are configuration, not hard-coded by category.
2. Facts extracted need to include their supporting evidence and location of the proposal. The current fixture includes only sample normalized facts, not the actual proposal text.
3. If mandatory test is unknown, it needs to be checked. In case of failure, it renders the proposal ineligible.
4. Text within a proposal that attempts to influence an automatic reviewer is untrusted document text, not system command.
5. Validation, eligibility test, scoring computations, tie breaking, and ranking are deterministic code.
6. A reviewer has the ability to clear flags, correct facts, or overturn a recommendation decision with explanation. The tool does not make the final decision on awarding the contract.

## Sample outcome

A and E are the only proposals to receive rankings in the offline sample. B is marked due to bidder-held licensing not being known. C is marked due to instructional-like content targeted for machine review and ambiguity about the five-year experience required in the proposal. D is marked due to incomplete duration data. Proposal B receives a temporary score, but not a rank, since the mandatory proof still needs to be resolved. Score is never considered to be an eligibility pass. The numerical ranking never satisfies an eligibility criteria requirement.

In this particular example only, any experience listed where projects were started in the calendar year 2021 will be considered as fulfilling the five-year sample window desired. In a production environment, an actual cut-off date would be used, rather than relying on period information..

## AI use statement

ChatGPT helped me formulate the workflow, come up with the extraction prompt, examine the scoring policy, and verify the calculation logic. An AI-generated draft of the answer was amended since it regarded the note resembling an instruction that appeared within the body of the proposal C as an instruction; however, any information contained within the proposal is to be considered untrusted data and thus is ignored and passed on to humans for evaluation. The lack of licence evidence for B is maintained as a review case.