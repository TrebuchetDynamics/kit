# Goal contract examples and audit worksheet

Use this reference when the objective is new, vague or high risk. The main skill
owns the workflow. This file supplies examples and field tests.

## Field tests

| Field | Test |
| --- | --- |
| Outcome | One end state. A reader can say "true" or "false" without asking what the user meant. |
| Verification | A command, test, artifact or source that an independent run can inspect. It names the expected result. |
| Constraints | A regression or invariant that a wrong fix could break. |
| Boundaries | Paths, data, tools, systems and resources the work may use. |
| Iteration | A rule for choosing the next action from the last result, not a fixed script. |
| Stop if | A condition that makes more attempts indefensible, and the input that would unlock progress. |

If a field cannot be written from the request and repository evidence, inspect the
repository first. Ask one question only when the answer changes the outcome, scope
or authority.

## Weak and strong goals

### Performance

Weak:

```text
Goal: Improve checkout performance
```

Strong:

```text
Goal contract
- Outcome: p95 checkout latency is below 120 ms on the checkout benchmark.
- Verification: `python bench.py checkout` reports p95 < 120 ms, and
  `pytest tests/checkout` passes.
- Constraints: The public checkout response shape and correctness suite stay unchanged.
- Boundaries: services/checkout and its tests only.
- Iteration: After each attempt, record the change and the new p95. Try the next
  smallest fix that the profile supports.
- Stop if: The benchmark cannot run, or two different fixes fail without a new lead.
  Report the evidence and the missing input.
```

### Migration

Weak:

```text
Goal: Migrate authentication to JWT
```

Strong:

```text
Goal contract
- Outcome: The auth service issues and accepts JWTs for all current login flows.
- Verification: `pytest tests/auth` passes, and the login smoke script returns a
  valid token for each supported client.
- Constraints: The `/login` response shape, session revocation and existing roles
  stay unchanged.
- Boundaries: services/auth, its tests and the local auth configuration.
- Iteration: Move one flow at a time. Run the focused auth test after each flow.
- Stop if: A database schema migration or a new secret is required. Report the exact
  change and the approval needed.
```

### Research

Weak:

```text
Goal: Reproduce the paper
```

Strong:

```text
Goal contract
- Outcome: A claim-by-claim report separates reproduced results, approximate
  reconstructions, blocked claims and remaining uncertainty.
- Verification: The report cites the paper section, local artifact and command for
  every claim, and the repository check for the report passes.
- Constraints: Do not describe an approximate result as an exact replay.
- Boundaries: The supplied paper, local data and installed tools. No paid service.
- Iteration: Build the claim inventory first. Test the claims that the available
  evidence can discriminate.
- Stop if: A claim needs missing source data or unavailable compute. Label it blocked
  and continue with independent claims.
```

### Documentation

Weak:

```text
Goal: Write docs for the feature
```

Strong:

```text
Goal contract
- Outcome: One page explains the feature, its lifecycle and two worked examples.
- Verification: The docs build passes, and every command in the page matches the
  current CLI help output.
- Constraints: Existing anchors and linked pages stay valid.
- Boundaries: docs/feature.md and the command reference it links.
- Iteration: Verify each command before adding the next section.
- Stop if: The current CLI behavior is unavailable. Report the missing runtime and
  leave the page unchanged.
```

## Read-only and investigation goals

A read-only goal has a report or evidence bundle as its outcome. Keep the same
fields. Set boundaries to read-only tools and name the files the report may create,
if any. Do not edit product code, tests, task records or documentation.

## Completion audit worksheet

| Contract criterion | Evidence | Fresh? | Result |
| --- | --- | --- | --- |
| Outcome | command, file@revision or artifact | yes/no | pass/fail/unknown |
| Verification | exact command and expected result | yes/no | pass/fail |
| Constraint 1 | test or inspection | yes/no | preserved/violated |
| Boundary 1 | changed-path or tool check | yes/no | respected/violated |

Then answer:

1. Which criterion lacks direct evidence?
2. Which check did not run?
3. Which result is stale because an input changed?
4. Which live, device, production or publication state remains unqualified?
5. Does the contract allow the remaining risk?

Complete only when every criterion has fresh evidence or the contract explicitly
accepts a named residual risk. Otherwise keep the goal active and continue or block.

## Authority

The invocation authorizes routine local work inside the contract. It does not add
authority for destructive actions, credentials, money, deployment, publication,
live operations or changes outside the stated boundaries. Those keep their own
rules and explicit approval.
