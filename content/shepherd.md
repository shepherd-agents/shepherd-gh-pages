---
title: "Shepherd: A Runtime Substrate Empowering Meta-Agents with a Formalized Execution Trace"
date: "2026-06-15"
description: "A Git-like, reversible execution trace that makes the harness just another agent."
authors:
  - { name: "Simon Yu",               url: "https://simonucl.github.io/",          affil: 1, equal: true, note: "* denotes equal contribution." }
  - { name: "Derek Chong",            url: "https://nlp.stanford.edu/~derekch/",   affil: 2, equal: true }
  - { name: "Ananjan Nandi",          url: "https://ananjan-nandi-9.github.io/",   affil: 2, equal: true }
  - { name: "Dilara Soylu",           url: "https://profiles.stanford.edu/dilara", affil: 2 }
  - { name: "Jiuding Sun",            url: "https://jiudingsun01.github.io/",      affil: 2, break_after: true }
  - { name: "Christopher D. Manning", url: "https://nlp.stanford.edu/~manning/",   affil: 2 }
  - { name: "Weiyan Shi",             url: "https://wyshi.github.io/",             affil: 1 }
affiliations:
  - { id: 1, name: "Northeastern University" }
  - { id: 2, name: "Stanford University" }
links:
  - { label: "Homepage", url: "https://shepherd-agents.ai/" }
  - { label: "Paper",    url: "https://arxiv.org/abs/2605.10913" }
  - { label: "alphaXiv", url: "https://www.alphaxiv.org/abs/2605.10913" }
  - { label: "Code",     url: "https://github.com/dcx/poc-crank-v2" }
  - { label: "X Thread (soon)" }
---

> [!tldr]
> A meta-agent watches, steers, or repairs other agents. Today it rebuilds everything by hand: read the transcripts, snapshot the environment, write one-off code to catch a bad write before it lands. The runtime hands it fragments, never the whole run.
>
> :shepherd: records every agent-environment interaction as a typed event in a Git-like trace, where any past state can be forked and replayed cheaply. That turns a meta-agent into a plain `@agent` that takes another agent's run as its argument. Deep Research put an agent *inside* the harness; :shepherd: makes the harness *out of* agents.
>
> We build three meta-agents on it. A live supervisor closes **91%** of the coordination gap on CooperBench, lifting pair pass rate from 28.8% to 54.7%. A counterfactual optimizer beats GEPA and MetaHarness on **4 of 5** benchmarks, in less wall-clock every time. Meta-agent-guided Tree-GRPO adds **+5.2 points** over flat GRPO on Qwen3.5-35B-A3B (and +3.4 on the larger Nemotron-3-Super-120B-A12B). A fork that carries its whole filesystem costs 134 to 143 ms, about **5x** cheaper than `docker commit`, and the core correctness argument is checked in Lean.

![**Figure 1.** Three meta-agents on one Shepherd substrate. (a) Multi-Agent Runtime Intervention: a supervisor watches two workers and resolves a conflict before it lands. (b) Counterfactual Meta-Optimization: an optimizer forks a finished run at the first changed step and replays it against a fixed baseline. (c) Meta-Agent-Guided Tree RL: a trainer forks K sibling rollouts mid-trajectory to read off per-step advantage.](../assets/fig-teaser.png)

## Motivation

What watches the harness? Right now, nothing. Your harness can pause an agent, fork it, and roll it back, yet it answers to no one, even though it makes your most expensive calls: what to retry, which attempt to keep, when to give up.

**Why it gets a pass.** Agent execution was never *data*. A run lives scattered across transcripts and environment snapshots, and the harness sits outside it as privileged host code. You can read the logs afterward. You can't pick the run up and branch it.

**What runtimes give you today.** OpenHands hands you a session's event stream. AgentGit gives the worker Git-like commit tools to checkpoint itself. BranchFS isolates the filesystem. Each is useful, and each is built for the agent that is *running*, not a second agent acting *on* it. None lets you take another :agent:'s whole execution, model state and environment and history at once, and branch it as one object. So every meta-agent rebuilds the same plumbing, and the real work, deciding when to step in, ends up frozen in orchestration code.

## The idea: agents all the way up

:shepherd: writes down what an agent does, as it does it. Every model call, tool call, and file write is recorded in a trace before it runs. The trace works like Git: you can branch it, jump back to any earlier point, and replay from there.

That changes what a harness is. Once a run is just data in a trace, the code that manages the run has no special status: it is an agent too, one whose input is another agent's run. A meta-agent over a meta-agent is the same construction again, which is where the name comes from: agents all the way up.

The system has four parts:

- A **task** is an agent. You write it as a plain Python function with an `@agent` decorator.
- An **effect** is one thing an agent does. It records the intent (the call it is about to make) before the result, which leaves room for a meta-agent to step in between the two.
- A **scope** is where an agent runs. Forking a scope copies the agent and its filesystem together in one cheap step.
- The **trace** is the run's history: a commit graph where any past state is reachable by its hash.

Underneath, the trace really is Git: `scope.fork()` is `git checkout -b`, `scope.merge()` is `git merge`, `scope.discard()` is `git branch -D`. The whole design comes down to one sentence: a meta-agent is a task that takes another task as its input, with no privileged control loop and no base class to subclass.

```python
from shepherd import agent, observe, revert, fork

@agent(LLM="haiku")
def implement(repo, feature):
    "Implement the feature in the repo"

@agent(LLM="opus", tool=[observe, revert, fork])
def oversee(run):
    "Watch the worker. If its tests break, revert to an earlier state and retry."

run         = implement(repo, "login")
implemented = oversee(run)   # the meta-agent manages the agent
```

`oversee` watches the effect stream without disturbing it, pushes effects in to intervene, checks out an earlier commit to rewind, and forks a scope to try something else. Because it is an agent like any other, a third agent can supervise the supervisor by taking `oversee`'s run as its input.^[One honest detail: not every effect can be undone. A filesystem write is reversible. A service write is compensable, through a handler you supply. A model call, a payment, an email: those are irreversible, recorded for audit but never un-sendable.]

<details>
<summary>The formal footing</summary>

Each construct maps onto a familiar building block: task = typed function, effect = algebraic effect, scope = region-scoped handler, trace = persistent data structure. The properties we care about (observing without perturbing, an atomic fork of agent and environment together, byte-identical revert and replay) rest on a small algebraic-effects trace machine we mechanized in Lean: forward simulation for the core fragment, trace monotonicity, and a single-child branch-replay skeleton. We mechanized the core correctness argument, not the production Python runtime, and the paper marks exactly where the verified boundary stops.

</details>

## System performance: forking, observing, and replaying

Everything below forks constantly. A supervisor forks the workers it watches, an optimizer forks a finished run at the step it edits, and the RL loop forks K siblings off every probed turn. The fork operation sits on the critical path, so the substrate has to make it cheap. This section describes how we built it and how we measured it.

The mechanism is to avoid copying the filesystem. Each :shepherd: scope is an OverlayFS mount, and `scope.fork()` adds a writable layer over the shared read-only ones. Nothing is copied up front: a branch pays only for the bytes it changes (copy-on-write), and `revert` discards the writable layer.

### Setup

We compare four ways to branch a running container's filesystem: a full root-fs copy (`tar`), `docker commit`, BranchFS, and :shepherd:'s overlay.^[We also measured a cloud-snapshot baseline (Modal's `snapshot_filesystem`); its numbers are in the paper.] The workloads are three real Terminal-Bench 2.0 Docker images spanning a 138x size range, at 42 MB, 200 MB, and 5.8 GB. All runs use a single 4 vCPU / 8 GB Linux host with docker and OverlayFS, 50 repetitions per cell, median reported. We time two operations, fork (standing up a usable branch) and revert (rolling a scope back to an earlier commit), and record the disk each fork consumes.

### Fork and revert latency

| Method | Fork 42 MB | Fork 200 MB | Fork 5.8 GB | Storage / fork |
|---|---|---|---|---|
| Full root-fs copy | 5,154 ms | 5,971 ms | 53,462 ms | up to 8.3 GB |
| docker commit | 658 ms | 692 ms | 725 ms | ~30 KB |
| BranchFS | 266 ms | 272 ms | 280 ms | ~12 KB |
| :smark: | **134 ms** | **135 ms** | **143 ms** | **~10 KB** |

The latency is flat in image size. Across a 138x range the fork time moves from 134 ms to 143 ms, because overlay cost scales with what a branch changes rather than with the image. That is roughly 5x faster than `docker commit` and up to 192x faster than a full copy on the 5.8 GB image, and at about 10 KB and 143 ms a fork is 2 to 3% of a single agent turn. Revert behaves the same way, at 140 to 147 ms.

### Observation overhead

A supervisor reads a worker by subscribing to its effect stream, which raises a fair question: does subscribing perturb the worker? It does not. We ran the same worker with and without a supervisor attached and compared its messages. They are identical, the same 21 messages and the same bytes, with zero added tokens in the worker's context. The stream is a read-side view of effects the kernel already records, so a supervised worker executes exactly as an unsupervised one.

### KV-cache reuse under replay

Because a fork preserves the byte-identical prefix of a run, replaying a branch presents the provider with the same prefix tokens in the same order, which it serves from its KV cache rather than recomputing. We measured the end-to-end hit rate on TB2 tasks with Haiku 4.5 through E2B, sweeping fork depth (10, 25, 50, and 75 steps) against branching factor K ∈ {1, 2, 4, 8}. From K=2 onward it settles near 95%. Forking K siblings mid-trajectory, which is what Tree-GRPO does on every probed turn, therefore adds little token cost on top of the disk cost.

> [!insight]
> Two properties account for the cost profile. Copy-on-write keeps a fork cheap on disk (about 10 KB and 143 ms even at 5.8 GB), and a byte-identical prefix keeps replaying that fork cheap at the provider (about 95% KV reuse). Together they let the meta-agents below fork on every step without the cost compounding.

## Results

Three meta-agents on one :shepherd: substrate, at three moments in an agent's life: while it runs, after it finishes, and while you train it.

### Multi-Agent Runtime Intervention

CooperBench documents an uncomfortable fact: two coding agents working in parallel on related features do *worse* than one agent doing both alone, because neither sees what the other is about to change. The remedy is a supervisor that watches both and steps in before a conflict lands.

**Setup.** Each task is a pair of related features in one repository. Two Claude Haiku 4.5 :worker:s run in forked scopes, one feature each, and a pair counts as solved only when both features pass their own pytest suite. We compare four conditions over 479 structurally conflicting pairs: one agent doing both features in sequence (the solo single-agent ceiling), two workers in parallel with no coordination, two workers passing peer-to-peer messages (the coop baseline), and two workers under a meta-agent (ours). The comparison that matters is managed against coop: a win there means supervising through the effect stream beats letting the workers message each other directly.

**The intervention loop.** The meta-agent, Claude Sonnet 4.6 or the stronger Opus 4.7, subscribes to both workers' effect streams. Observation is a read-side view of the trace, so watching both workers adds nothing to their context (the zero-token result from the system-performance section). Every few seconds the meta-agent inspects what each worker is about to do and picks one of three actions: `inject` a note into a worker's context to redirect it, `handoff` one worker's finished scope to the other as its starting point so the second builds on the first instead of colliding with it, or `discard` a worker that has wedged itself and restart it from a clean fork. None of this touches the workers' code or the framework. The supervisor is an ordinary agent whose input is the pair's run.

**Results.** The coop baseline reaches 28.8%, well short of the 57.2% solo ceiling: peer messages alone do not keep two agents out of each other's way. A Sonnet supervisor lifts the pass rate to 45.3% and an Opus supervisor to 54.7%. By the gap arithmetic, (54.7 - 28.8) / (57.2 - 28.8), the Opus meta-agent recovers **91%** of the coordination gap, at 1 to 5 minutes of supervision overhead per pair.^[A proof of existence that the substrate enables live supervision, not a like-for-like compute win.]

![**Figure 2.** A meta-agent supervisor recovers most of the coordination gap on CooperBench. Left: pair pass rate (coop 28.8%, +Sonnet 45.3%, +Opus 54.7%; solo single-agent ceiling 57.2%). Right: wall-clock per pair, with the meta-agent's overhead hatched.](../assets/fig-supervision.png)

The two supervisors reach for different tools. Counting pairs where each action fires at least once, the Opus meta-agent injects on 39.2% of pairs, hands off on 31.5%, and discards rarely (4.6%): it prefers to nudge and to reuse work. The weaker Sonnet supervisor intervenes less (26.4% inject, 18.7% handoff) but pulls the kill switch more often (7.9% discard), which reads as a less capable supervisor leaning on the blunt action when the precise ones are harder to land.

![**Figure 3.** The stronger supervisor intervenes more and kills less. How often each meta-agent uses inject, handoff, and discard, as a share of the pairs where it fired the tool at least once.](../assets/fig-strategies.png)

> [!insight]
> Two parallel agents that sabotage each other are a known failure. A supervisor that watches both effect streams and steps in, written as an ordinary agent rather than a change to the framework, recovers almost all of the gap.

### Counterfactual Meta-Optimization

When a workflow fails, the fault is usually a few bad calls out of many. The obvious way to test a fix is to patch the workflow and run it again, but a fresh run also draws fresh randomness, so a better score might be your edit or might be the dice. Optimizers that re-run from scratch spend much of their budget fighting that noise.

**Setup.** We compare counterfactual replay (CRO) against two optimizers, GEPA and MetaHarness, on five benchmarks: HoVer, MATH, IFBench, LiveCodeBench, and TerminalBench 2.0. GPT-5.4-mini runs the workflow being optimized and GPT-5.4 is the optimizer that proposes edits. For each method we record the held-out pass rate and the wall-clock minutes it spends optimizing.

**How CRO works.** CRO holds everything constant except the edit. It takes a finished run, forks the trace at the first commit the edit touches, and replays only the suffix from there, against the byte-identical prefix as a fixed baseline. Every candidate is scored on the same frozen history, so a score change reflects the edit alone, not a different roll of the dice. The shared prefix replays from the provider's KV cache (the system-performance result), so each evaluation stays cheap.

**Results.** CRO takes 4 of the 5 benchmarks, with both the highest held-out score and the lowest wall-clock on those four.

| Method | HoVer | MATH | IFBench | LiveCodeBench | TB-2 (avg@5) |
|---|---|---|---|---|---|
| Baseline | 43.7±0.0 | 60.7±1.2 | 42.4±1.8 | 30.7±2.1 | 31.2 |
| GEPA | 43.7±0.0 (67) | 74.0±3.5 (20) | 50.1±1.2 (50) | 48.7±1.5 (73) | 31.2 (157) |
| MetaHarness | 77.8±0.4 (235) | 79.3±1.2 (101) | **52.3±1.4** (126) | 40.0±3.6 (217) | 31.2 (173) |
| :cro: | **79.4±0.2** (120) | **80.0±2.0** (42) | 51.3±1.1 (82) | **51.0±1.7** (117) | **35.2** (73) |

*Test pass-rate mean ± std; optimization minutes in parentheses; bold = best per row. CRO's wall-clock lead over MetaHarness reaches ~58% on MATH (42 vs 101 min). On execution-heavy TB-2, neither GEPA nor MetaHarness beats the 31.2 baseline, while CRO reaches 35.2 (+4 points) at the least wall-clock. The one near-tie is IFBench: MetaHarness edges CRO inside a std (52.3 vs 51.3), and CRO still does it in less time, 82 vs 126 minutes.*

![**Figure 4.** Counterfactual Meta-Optimization reaches a higher held-out score in less wall-clock on LiveCodeBench: CRO at 51.0, past GEPA (48.7), MetaHarness (40.0), and the 30.7 baseline.](../assets/fig-cro.png)

> [!insight]
> Because a fork keeps the byte-identical prefix, CRO judges every edit against a fixed baseline instead of a noisy from-scratch re-run. That is both cheaper and more honest than re-optimizing from zero.

### Meta-Agent-Guided Tree RL

RL on long-horizon agent tasks is starved for signal. The reward is one bit, at the very end, so flat GRPO is slow to learn which of the dozens of turns actually mattered.

**Setup.** Training runs in two phases. First, rollout collection: the base policy runs on terminal-agent tasks from the Endless Terminals corpus inside E2B or Daytona sandboxes. At selected turns the meta-agent forks the scope and samples K=4 sibling continuations from that exact state, each played to completion, and saves the resulting tree. Second, training: the trees feed a GRPO trainer (SLIME on Modal H100s) whose advantages come from the spread across shared-prefix siblings, so there is no separate value model and no process reward model. Flat GRPO and Tree-GRPO run on matched generation compute (same token budget, same rollout steps), so the tree structure adds signal without adding compute.

**Why the forks help.** Two siblings that share a prefix and diverge at one turn give a per-step counterfactual: the difference in their final rewards is what that turn was worth. That is the credit-assignment signal flat GRPO lacks, recovered from the same one-bit reward. And because forked branches reuse the byte-identical prefix, the extra continuations replay largely from the KV cache (the system-performance result), so collecting a K-way tree costs little more than a single rollout.

![**Figure 5.** Tree-GRPO pulls ahead of flat GRPO as training proceeds. Mean training reward over rollout steps, for both models.](../assets/fig-treegrpo.png)

**Results.** Out-of-distribution transfer to TerminalBench 2.0 (avg@5 over 89 tasks, 5 seeds), a suite never seen in training:

| Model | Base | Flat GRPO | :treegrpo: |
|---|---|---|---|
| Qwen3.5-35B-A3B | 26.1±4.21 | 34.2±4.05 | **39.4±3.87** (+5.2) |
| Nemotron-3-Super-120B-A12B | 30.3±3.62 | 33.8±3.41 | **37.2±3.19** (+3.4) |

*Out-of-distribution transfer to TerminalBench 2.0, avg@5 (%); +gain is vs flat GRPO. The Qwen3.5 +5.2 clears its ~3.9 to 4.1 std comfortably.*^[The Nemotron +3.4 only just edges past its ~3.2 to 3.4 std, a slim margin rather than a clean separation.]

> [!insight]
> Same generation budget, same recipe, same task set. The only change is forking sibling branches mid-rollout to read off per-step advantage, and it is worth a few points on a hard OOD benchmark.

### Post-hoc Trajectory Compression

This one lives in the appendix, but it falls out of the same machinery. A passing agent run is usually longer than it needs to be: dead ends, re-reads, paths abandoned halfway. Because a finished run is a replayable trace, we can ask a sharper question than "did it pass": does a strictly shorter passing run exist?

**Setup.** We start from passing baselines by two coding agents, Claude Sonnet 4.6 and GPT-5.4, on SWE-Bench Verified and TerminalBench 2.0. A meta-agent reads the finished trace, proposes a shorter path that drops the steps it judges unnecessary, and we replay that path on the same task. It counts as a compression only if the shorter run is verified to still pass.

**Results.** A shorter passing run exists more often than not. On SWE-Bench Verified, 68% of Sonnet and 82% of GPT-5.4 passing baselines admit one; on TerminalBench 2.0 it is 77% and 68%. When a run does compress, it compresses hard: mean Sonnet length on SWE-Bench Verified drops from 21.4 to 8.9 model calls.

![**Figure 6.** Most passing runs admit a strictly shorter passing rerun. Left: the share that compress, by model and benchmark. Right: mean model calls before and after.](../assets/fig-trajprune.png)

## FAQ

<details>
<summary>Does Shepherd run on Linux, macOS, and Windows?</summary>

The copy-on-write fork is built on Linux OverlayFS, so the substrate runs natively on Linux. On macOS and Windows you run it through a Linux sandbox, which is also how you get a clean, reproducible environment per agent. First-class macOS and Windows support is on the roadmap; see the [docs](https://docs.shepherd-agents.ai/) for current status.

</details>

<details>
<summary>What does a fork actually capture?</summary>

Everything the agent needs to continue from that exact point: the filesystem (as a copy-on-write overlay), the agent's message history and model context, and its position in the execution trace. `scope.fork()` copies the agent and its environment together in one step, so a branch is a complete, runnable continuation rather than just a filesystem snapshot.

</details>

<details>
<summary>Which sandbox backends are supported?</summary>

E2B, Daytona, and Modal today, through pluggable device adapters, with more to come. The substrate talks to a sandbox through a small `Device` interface (checkpoint, revert, exec), so adding a backend means writing one adapter, not touching the core.

</details>

<details>
<summary>Why "Shepherd," and why a sheep?</summary>

Because a shepherd is exactly the job. A real shepherd doesn't do the grazing: it watches the flock, keeps the sheep on track, and steps in when one wanders toward a cliff. That is what a meta-agent does for your worker agents. It watches the run, nudges a stray back, and pulls one out of trouble before it falls. The logo is a sheep in a little hat, the same animal as the workers, just the one keeping an eye on the rest. And yes, we also think it's cute.

</details>

## Try it

```bash
# 1 · install
pip install shepherd-ai
shepherd init

# 2 · add a coding-agent plugin
shepherd plugin install claude-code      # or: shepherd plugin install codex

# 3 · run it; every step is a commit
shepherd run claude "fix the login bug"

# 4 · went wrong? roll back like git
shepherd log
shepherd revert 4
```

`shepherd log` reads the execution trace like `git log`: every model call, tool call, and file edit is a commit.

```text
*  6  e8f1a2c  tool   · pytest tests/              ✗ 2 failed
*  5  3b9d40e  edit   · auth/session.py   +18 -4
*  4  a1c77f2  tool   · pytest tests/              ✓ 41 passed
*  3  9f4e2a1  edit   · auth/login.py     +12 -3
*  2  7c8d5b0  tool   · grep -rn "session" auth/
*  1  c0ffee1  model  · plan: fix the login bug
*  0  0a2b8c1  run    · claude "fix the login bug"   (root)
```

`shepherd revert 4` puts the agent and its filesystem back to commit 4, byte for byte, and drops the regression at commit 5. You are back to green.

📦 [**PyPI**](https://pypi.org/project/shepherd-ai/0.0.1/)  |  💻 [**Code**](https://github.com/dcx/poc-crank-v2)

So the interesting question isn't ours: what would you build with a harness you can fork and rewind?

## Acknowledgments

Thanks to our early readers for their feedback.

```bibtex
@misc{yu2026shepherdruntimesubstrateempowering,
  title={Shepherd: A Runtime Substrate Empowering Meta-Agents with a Formalized Execution Trace},
  author={Simon Yu and Derek Chong and Ananjan Nandi and Dilara Soylu and Jiuding Sun and Christopher D Manning and Weiyan Shi},
  year={2026},
  eprint={2605.10913},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2605.10913}
}
```
