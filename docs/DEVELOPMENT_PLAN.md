# ChainC2 Sentinel — Development Plan

## Project

ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels.

The project is a defensive cybersecurity research framework developed in a controlled laboratory environment. All blockchain activity, endpoint activity, network activity, and simulated scenarios are intended for safe local experimentation.

---

# Development Structure

The implementation is divided into three phases.

Each phase spans approximately two weeks.

Each week must contain a minimum of three meaningful Git commits representing genuine implementation, testing, documentation, or integration work.

A phase is considered complete only after its implementation has been tested, integrated, and documented.

---

# Phase 1 — Controlled Laboratory & Telemetry

## Weeks 1–2

### Objective

Establish the controlled laboratory environment and collect telemetry across the endpoint, blockchain/RPC, and network layers.

### Components

- Local Hardhat EVM environment
- Synthetic Solidity contracts
- Deployment and contract tests
- Common SentinelEvent telemetry schema
- RPC monitoring
- Endpoint telemetry
- Network telemetry
- Controlled HTTP target
- Synthetic test scenarios
- Docker-based isolated laboratory
- Integration tests

### Current Progress

- Milestone 1 — Development environment and project structure: COMPLETED
- Milestone 2 — Synthetic blockchain contracts and tests: COMPLETED
- Milestone 3 onward: NOT STARTED

### Current Git Status

Milestone 1 and Milestone 2 changes are currently in the working tree and have not yet been committed.

Do not combine unrelated milestones into a single commit.

---

# Phase 2 — Correlation & Detection

## Weeks 3–4

### Objective

Transform the collected telemetry into a defensive correlation and detection framework.

### Components

- Event ingestion
- Event normalization
- Temporal correlation
- Endpoint-to-RPC correlation
- RPC-to-blockchain correlation
- Blockchain-to-network correlation
- Evidence-chain construction
- Behavioral features
- Detection logic
- Suspicion scoring
- Explainable detection output
- Detection validation

The detection approach must be justified using the characteristics of the collected telemetry rather than assuming a particular algorithm in advance.

---

# Phase 3 — Evaluation & Analysis

## Weeks 5–6

### Objective

Evaluate the framework experimentally and produce reproducible results.

### Components

- Automated scenario execution
- Evaluation pipeline
- Detection metrics
- False-positive analysis
- Detection-latency analysis
- Legitimate Web3 baseline comparison
- Results visualization
- Evidence-chain visualization
- Dashboard/reporting
- Experimental documentation
- Limitations and future work

All reported results must come from actual experiments. No fabricated metrics or results.

---

# Git Development Rules

## Weekly Development

Maintain a minimum of three meaningful commits per week.

Commits must represent genuine project progress.

Examples:

- `feat:` new functionality
- `test:` new or improved tests
- `docs:` meaningful documentation
- `fix:` correction of an identified problem
- `chore:` meaningful infrastructure/configuration work

Do not create artificial commits simply to satisfy a commit count.

---

# Phase Checkpoints

At the completion of each two-week phase:

1. Verify the implementation.
2. Run the relevant tests.
3. Update documentation.
4. Review the repository structure.
5. Confirm no credentials or confidential data are present.
6. Create the appropriate review tag.

Tags:

- `review-1` — Phase 1 completion
- `review-2` — Phase 2 completion
- `final` — Phase 3 completion

A phase checkpoint represents the verified state of the repository at that point in development.

---

# Git Safety Rules

- Do not use `git add .` blindly when separating milestones.
- Do not combine unrelated milestone work into one commit.
- Do not create artificial or empty commits.
- Do not commit credentials, API keys, `.env` files, licensed datasets, or confidential institutional data.
- Do not push unless the repository state has been reviewed.
- Do not create or modify Git history without an explicit development decision.
- Preserve the ability to identify the exact state of the project at each phase checkpoint.

---

# Current Project Position

**Phase:** Phase 1 — Controlled Laboratory & Telemetry

**Week:** Week 1

**Completed Milestones:**

- Milestone 1 — Project configuration and development infrastructure
- Milestone 2 — Synthetic blockchain contracts and contract tests

**Current State:**

The Milestone 1 and Milestone 2 implementation exists locally but has not yet been committed.

### Next Development Target

Continue Phase 1 implementation with the telemetry foundation.

Milestone 1 and Milestone 2 have been completed locally and will be
incorporated into the planned progressive Git history at the appropriate
development checkpoint.

The next implementation target is the telemetry foundation, including:

- Common `SentinelEvent` telemetry schema
- RPC monitoring
- Endpoint telemetry
- Network telemetry
- Controlled HTTP target
- Synthetic test scenarios
- Docker-based isolated laboratory
- Integration tests

**Git checkpoint:** Not created yet.

**Do not create a Git commit or push to GitHub unless explicitly instructed.**