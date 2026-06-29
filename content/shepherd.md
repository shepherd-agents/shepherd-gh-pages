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
  - { label: "Docs",     url: "https://docs.shepherd-agents.ai/" }
  - { label: "X Thread (soon)" }
---

> [!tldr]
> As agents take on more complex tasks, **meta-agents** are becoming increasingly important: higher-order agents that create, operate on, and manage other agents. But today, writing a meta-agent means managing execution state by hand, reconstructing it from LLM transcripts and final environment state.
>
> :shepherd: draws on functional programming to keep an agent's whole execution as a reversible, Git-like trace: one you can branch, roll back to any previous state, and replay. A meta-agent then simply becomes an agent that operates on another agent's definition and trace.
>
> We build three meta-agents on it. **(1)** A live supervisor closes **91%** of the coordination gap on CooperBench, from 28.8% to 54.7%. **(2)** A counterfactual optimizer beats GEPA and MetaHarness, by up to **+11%** on LiveCodeBench and with less runtime. **(3)** Meta-agent-guided Tree-GRPO adds **+5.2%** over flat GRPO on Terminal-Bench 2.0. Underneath, a whole-filesystem fork costs about 140 ms, roughly **5x** cheaper than `docker commit`.
>
> **Resources** &nbsp; <img class="rsrc" src="../assets/logo-shepherd.png" alt="">[Homepage](https://shepherd-agents.ai/) &nbsp;·&nbsp; <img class="rsrc" src="../assets/icon-arxiv.svg" alt="">[Paper](https://arxiv.org/abs/2605.10913) &nbsp;·&nbsp; <img class="rsrc" src="../assets/icon-alphaxiv.png" alt="">[alphaXiv](https://www.alphaxiv.org/abs/2605.10913) &nbsp;·&nbsp; <img class="rsrc" src="../assets/icon-github.svg" alt="">[Code](https://github.com/dcx/poc-crank-v2) &nbsp;·&nbsp; <img class="rsrc" src="../assets/icon-docs.svg" alt="">[Docs](https://docs.shepherd-agents.ai/) &nbsp;·&nbsp; <img class="rsrc" src="../assets/icon-x.svg" alt="">Tweet

![**Figure 1.** Three meta-agents built on Shepherd, three examples of many. *Top:* a meta-agent is a plain function over another agent's run; it observes, intercepts, forks, and reverts the worker through a shared trace, here catching a buggy edit and forking to a passing continuation. *Bottom:* headline results. (a) Multi-Agent Runtime Intervention lifts CooperBench pair pass rate to 54.7%; (b) Counterfactual Optimization beats GEPA and MetaHarness on LiveCodeBench; (c) Meta-Agent-Guided Tree RL adds +5.2% on Terminal-Bench 2.0.](../assets/fig-teaser.png)

# Motivation

Look at how the current agentic systems get built now: each puts a higher-order agent, a **meta-agent**, in charge of the others.^[Examples like: Anthropic's Claude Code composes [dynamic workflows](https://code.claude.com/docs/en/workflows) of sub-agents, Nous Research's Hermes delegates to [agent teams](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation), and Kimi K2.5 coordinates an [agent swarm](https://arxiv.org/abs/2602.02276).] These meta-agents are becoming central to getting real work out of agentic systems. To do their job, these meta-agents reach for the same few operations on the agent underneath: **observe** it as it runs, **fork** it before a risky step, **revert** it on failure, **modify** it to fix the bug, and **resume**. Today's substrates are not built for that. Most agent frameworks only expose transcripts and environment snapshots, so every meta-agent reinvents the same components: parsing logs, hand-rolling environment checkpoints, re-running with patched code just to rebuild environment state.

Existing runtimes each give you a piece. OpenHands exposes a session's event stream. AgentGit gives the worker Git-like commit tools to checkpoint itself. BranchFS isolates the filesystem. Every one is built for the agent that is *running*. None is built for a second agent acting *on* it: none lets you operate on another :agent:'s whole execution and definition as data.

| Method | Intercept execution | Fork agent + env | Revert to past state | Modify behavior |
|---|:---:|:---:|:---:|:---:|
| BranchFS | ○ | ◐ | ◐ | ○ |
| Docker | ○ | ◐ | ◐ | ○ |
| OpenHands | ◐ | ◐ | ◐ | ○ |
| AgentGit | ○ | ◐ | ◐ | ○ |
| :smark: | ● | ● | ● | ● |

*● full · ◐ partial · ○ none. Existing runtimes cover pieces of what a meta-agent needs; :shepherd: is the only one where a second agent can intercept and modify a running agent, while the rest can only snapshot its files.*

# :shepherd:: your harness is just another agent

A meta-agent operates on another agent's run while it happens: it watches the run, branches it to try an alternative, rolls it back when it fails, patches it, and lets it keep going. That only works if the run is something you can hold and manipulate, like a Git repo. So :shepherd: records everything an agent does, every model call, tool call, and file write, as a commit in a Git-like trace that a meta-agent can read, branch, and rewind.

The system has four parts:

| Part | What it is | In FP terms |
|---|---|---|
| **Task** | An agent, written as a plain Python function with an `@task` decorator. | a typed function |
| **Effect** | One thing an agent does. It records the intent (the call it is about to make) before the result, leaving room for a meta-agent to step in between the two. | an algebraic effect |
| **Scope** | Where an agent runs. Forking a scope copies the agent and its filesystem together in one cheap step. | a scoped effect handler |
| **Trace** | The run's history: a commit graph where any past state is reachable by its hash. | a persistent data structure |

A meta-agent operates on that trace the way you operate on a Git repo:

| What you'd do to a repo | What :shepherd: does to a run |
|---|---|
| `git checkout -b` | fork the agent **and its environment** to try an alternative |
| `git merge` | keep the branch that worked |
| `git branch -D` | throw away the one that didn't |
| `git log` | read every model call, tool call, and edit as commits |

The payoff is one line: because both the agent and its run are now data, a meta-agent is just a function that takes another agent's run as its argument, composed and called like any other task.

```python
from shepherd import task, workspace
from shepherd.providers import claude

@task
def implement(repo, feature) -> str:
    "Implement the feature in the repo."

@task
def oversee(child, repo, feature) -> str:
    "Watch the worker. If its tests fail, revert to the last green commit and retry."

with workspace(model=claude("sonnet-4-5")):
    result = oversee(implement, repo, "login")   # the meta-agent manages the worker
```

`oversee` watches the effect stream without disturbing it, pushes effects in to intervene, checks out an earlier commit to rewind, and forks a scope to try something else. Because it is an agent like any other, a third agent can supervise the supervisor by taking `oversee`'s run as its input.

**The life of an effect.** The split between intent and result is what makes the rest work. When an agent is about to call a tool, it first emits the *intent* as an effect; the kernel records it, and any subscribed meta-agent sees it on the stream. Only then does the call run, and its *outcome* is written back to the same effect. That ordering is why a supervisor can observe without perturbing (it reads intents the worker already emits) and intervene before damage lands (it acts in the gap between intent and result).

<details markdown="1">
<summary>The functional-programming view</summary>

The mapping in the table above is exact, and the properties a meta-agent relies on fall straight out of it. Algebraic effects are why observation never perturbs the worker and interception is possible at all: the intent exists as a value on the stream before the action runs. Scoped handlers are why a fork is a clean, nestable branch that merges back or is discarded as a unit. A persistent, content-addressed trace is why any past state replays byte for byte instead of being rebuilt from a log.

The deterministic core of this calculus is mechanized in Lean, which lets us state the replay and revert guarantees precisely instead of by convention.

</details>

# Infrastructure: :shepherd:'s System Performance

A meta-agent leans on the same handful of operations: it observes a worker, forks it to try an alternative, reverts on failure, and replays a branch against the model's cache. For any of that to be worth doing at runtime, each operation has to be cheap enough to use without a second thought. This section measures the three that sit on the critical path.

The one that has to be cheapest is the fork, since the meta-agents below fork constantly: a supervisor forks the workers it watches, an optimizer forks a finished run at the step it edits, and the RL loop forks K siblings off every probed turn. The mechanism is to avoid copying the filesystem. Each :shepherd: scope is an OverlayFS mount, and `scope.fork()` adds a writable layer over the shared read-only ones. Nothing is copied up front: a branch pays only for the bytes it changes (copy-on-write), and `revert` discards the writable layer.

#### Setup

We compare four ways to branch a running container's filesystem: a full root-fs copy (`tar`), `docker commit`, BranchFS, and :shepherd:'s overlay.^[We also measured a cloud-snapshot baseline (Modal's `snapshot_filesystem`). The Docker images are pre-built task environments from [Terminal-Bench 2.0](https://arxiv.org/abs/2601.11868) (Merrill et al., 2026).] The workloads are three real Terminal-Bench 2.0 Docker images spanning a 138x size range, at 42 MB, 200 MB, and 5.8 GB. All runs use a single 4 vCPU / 8 GB Linux host with docker and OverlayFS, 50 repetitions per cell, median reported. We time two operations, fork (standing up a usable branch) and revert (rolling a scope back to an earlier commit), and record the disk each fork consumes.

#### Fork and revert latency

| Method | Fork 42 MB | Fork 200 MB | Fork 5.8 GB | Storage / fork |
|---|---|---|---|---|
| Full root-fs copy | 5,154 ms | 5,971 ms | 53,462 ms | up to 8.3 GB |
| docker commit | 658 ms | 692 ms | 725 ms | ~30 KB |
| BranchFS | 266 ms | 272 ms | 280 ms | ~12 KB |
| :smark: | **134 ms** | **135 ms** | **143 ms** | **~10 KB** |

The latency is flat in image size. Across a 138x range the fork time moves from 134 ms to 143 ms, because overlay cost scales with what a branch changes rather than with the image. That is roughly 5x faster than `docker commit` and up to 192x faster than a full copy on the 5.8 GB image, and at about 10 KB and 143 ms a fork is 2 to 3% of a single agent turn. Revert behaves the same way, at 140 to 147 ms.

#### Observation overhead

A supervisor reads a worker by subscribing to its effect stream, which raises a fair question: does subscribing perturb the worker? It does not. We ran the same worker with and without a supervisor attached and compared its messages. They are identical, the same 21 messages and the same bytes, with zero added tokens in the worker's context. The stream is a read-side view of effects the kernel already records, so a supervised worker executes exactly as an unsupervised one.

#### KV-cache reuse under replay

Because a fork preserves the byte-identical prefix of a run, replaying a branch presents the provider with the same prefix tokens in the same order, which it serves from its KV cache rather than recomputing. We measured the end-to-end hit rate on TB2 tasks with Haiku 4.5, sweeping fork depth (10, 25, 50, and 75 steps) against branching factor K ∈ {1, 2, 4, 8}. From K=2 onward it settles near 95%. Forking K siblings mid-trajectory, which is what Tree-GRPO does on every probed turn, therefore adds little token cost on top of the disk cost.

> [!insight]
> Shepherd keeps a fork cheap on disk (about 10 KB and 143 ms even at 5.8 GB), and a byte-identical prefix keeps replaying that fork cheap at the provider (about 95% KV reuse). Together they let the meta-agents below fork on every step without the cost compounding.

# Experiments

Here are three meta-agents we built on :shepherd:, at three moments in an agent's life. They are examples; the same handful of operations supports many more. Each is a plain agent, and each leans on a different substrate property.

| When | Meta-agent | Substrate property it leans on |
|---|---|---|
| While agents run | Multi-Agent Runtime Intervention | Observe |
| After agents finish | Counterfactual Meta-Optimization | Replay |
| While training agents | Meta-Agent-Guided Tree RL | Fork |

![**Figure 2.** How each meta-agent acts on the execution trace. (a) Multi-Agent Runtime Intervention observes two workers and intervenes before a conflict lands; (b) Counterfactual Meta-Optimization forks at the edited commit and replays only the suffix; (c) Meta-Agent-Guided Tree RL forks K sibling rollouts at a chosen turn.](../assets/fig-mechanisms.png)

#### Multi-Agent Runtime Intervention

CooperBench documents a fact: two coding agents working in parallel on related features do *worse* than one agent doing both alone, because neither sees what the other is about to change. The remedy is a supervisor that watches both and steps in before a conflict lands.

**Setup.** Each task is a pair of related features in one repository. Two Claude Haiku 4.5 :worker:s run in forked scopes, one feature each, and a pair counts as solved only when both features pass their own pytest suite. We compare four conditions over 479 structurally conflicting pairs: one agent doing both features in sequence (the solo single-agent ceiling), two workers in parallel with no coordination, two workers passing peer-to-peer messages (the coop baseline), and two workers under a meta-agent (ours). The comparison that matters is managed against coop: a win there means supervising through the effect stream beats letting the workers message each other directly.

**The intervention loop.** The meta-agent, Claude Sonnet 4.6 or the stronger Opus 4.7, subscribes to both workers' effect streams. Observation is a read-side view of the trace, so watching both workers adds nothing to their context (the zero-token result from the overhead section). Every few seconds the meta-agent inspects what each worker is about to do and picks one of three actions: `inject` a note into a worker's context to redirect it, `handoff` one worker's finished scope to the other as its starting point so the second builds on the first instead of colliding with it, or `discard` a worker that has wedged itself and restart it from a clean fork. None of this touches the workers' code or the framework. The supervisor is an ordinary agent whose input is the pair's run.

**Results.** The coop baseline reaches 28.8%, well short of the 57.2% solo ceiling: peer messages alone do not keep two agents out of each other's way. A Sonnet supervisor lifts the pass rate to 45.3% and an Opus supervisor to 54.7%. By the gap arithmetic, (54.7 - 28.8) / (57.2 - 28.8), the Opus meta-agent recovers **91%** of the coordination gap, at 1 to 5 minutes of supervision overhead per pair.^[A proof of existence that the substrate enables live supervision.]

![**Figure 3.** A meta-agent supervisor recovers most of the coordination gap on CooperBench. Left: pair pass rate (coop 28.8%, +Sonnet 45.3%, +Opus 54.7%; solo single-agent ceiling 57.2%). Right: wall-clock per pair, with the meta-agent's overhead hatched.](../assets/fig-supervision.png)

The two supervisors reach for different tools. Counting pairs where each action fires at least once, the Opus meta-agent injects on 39.2% of pairs, hands off on 31.5%, and discards rarely (4.6%): it prefers to nudge and to reuse work. The weaker Sonnet supervisor intervenes less (26.4% inject, 18.7% handoff) but pulls the kill switch more often (7.9% discard), which reads as a less capable supervisor leaning on the blunt action when the precise ones are harder to land.

![**Figure 4.** The stronger supervisor intervenes more and kills less. How often each meta-agent uses inject, handoff, and discard, as a share of the pairs where it fired the tool at least once.](../assets/fig-strategies.png)

> [!insight]
> Meta-agents in :shepherd: close **91%** of CooperBench's coordination gap: they supervise parallel agents without perturbing them, and add only minimal runtime overhead.

#### Counterfactual Meta-Optimization

When a workflow fails, the fault is usually a few bad calls out of many. The obvious way to test a fix is to patch the workflow and run it again, but a fresh run also draws fresh randomness, so a better score might be your edit or might be the dice. Optimizers that re-run from scratch spend much of their budget fighting that noise.

**Setup.** We compare counterfactual replay (CRO) against two optimizers, GEPA and MetaHarness, on five benchmarks: HoVer, MATH, IFBench, LiveCodeBench, and TerminalBench 2.0. GPT-5.4-mini runs the workflow being optimized and GPT-5.4 is the optimizer that proposes edits. For each method we record the held-out pass rate and the wall-clock minutes it spends optimizing.

**How CRO works.** CRO holds everything constant except the edit. It takes a finished run, forks the trace at the first commit the edit touches, and replays only the suffix from there, against the byte-identical prefix as a fixed baseline. Every candidate is scored on the same frozen history, so a score change reflects the edit alone, not a different roll of the dice. The shared prefix replays from the provider's KV cache (the KV-cache result above), so each evaluation stays cheap.

**Results.** CRO takes 4 of the 5 benchmarks, with the highest held-out score and the lowest wall-clock on each. The margins are widest where exploration matters most: it scores 27.5% higher than MetaHarness on LiveCodeBench (51.0 vs 40.0), and on execution-bound TerminalBench 2.0, where neither GEPA nor MetaHarness beats the baseline at all, it lifts the score by 4 points (12.8%) at the least wall-clock of any method.

| Method | HoVer | MATH | IFBench | LiveCodeBench | TB-2 (avg@5) |
|---|---|---|---|---|---|
| Baseline | 43.7±0.0 | 60.7±1.2 | 42.4±1.8 | 30.7±2.1 | 31.2 |
| GEPA | 43.7±0.0 (67) | 74.0±3.5 (20) | 50.1±1.2 (50) | 48.7±1.5 (73) | 31.2 (157) |
| MetaHarness | 77.8±0.4 (235) | 79.3±1.2 (101) | **52.3±1.4** (126) | 40.0±3.6 (217) | 31.2 (173) |
| :cro: | **79.4±0.2** (120) | **80.0±2.0** (42) | 51.3±1.1 (82) | **51.0±1.7** (117) | **35.2** (73) |

*Test pass-rate mean ± std; optimization minutes in parentheses; bold = best per column. CRO's wall-clock lead over MetaHarness reaches ~58% on MATH (42 vs 101 min). On execution-heavy TB-2, neither GEPA nor MetaHarness beats the 31.2 baseline, while CRO reaches 35.2 (+4 points) at the least wall-clock. The one near-tie is IFBench: MetaHarness edges CRO inside a std (52.3 vs 51.3), and CRO still does it in less time, 82 vs 126 minutes.*

![**Figure 5.** Counterfactual Meta-Optimization reaches a higher held-out score in less wall-clock on LiveCodeBench: CRO at 51.0, past GEPA (48.7), MetaHarness (40.0), and the 30.7 baseline.](../assets/fig-cro.png)

> [!insight]
> Meta-agents in :shepherd: optimize workflows better than GEPA and MetaHarness, because byte-identical replay on trajectories lets them run counterfactual meta-optimization. They beat baselines on **4 of 5** benchmarks at lower wall-clock.

#### Meta-Agent-Guided Tree RL

RL on long-horizon agent tasks is starved for signal. The reward is one bit, at the very end, so flat GRPO is slow to learn which of the dozens of turns actually mattered.

**Setup.** Training runs in two phases. First, rollout collection: the base policy runs on terminal-agent tasks from the Endless Terminals corpus inside E2B or Daytona sandboxes. At selected turns the meta-agent forks the scope and samples K=4 sibling continuations from that exact state, each played to completion, and saves the resulting tree. Second, training: the trees feed a GRPO trainer (SLIME on Modal H100s) whose advantages come from the spread across shared-prefix siblings, so there is no separate value model and no process reward model. Flat GRPO and Tree-GRPO run on matched generation compute (same token budget, same rollout steps), so the tree structure adds signal without adding compute.

**Why the forks help.** Two siblings that share a prefix and diverge at one turn give a per-step counterfactual: the difference in their final rewards is what that turn was worth. That is the credit-assignment signal flat GRPO lacks, recovered from the same one-bit reward. And because forked branches reuse the byte-identical prefix, each sibling pays only for its own suffix while the shared prefix resolves from the KV cache (the KV-cache result above). A K-way tree therefore costs about K extra suffixes, not K full rollouts.

![**Figure 6.** Tree-GRPO pulls ahead of flat GRPO as training proceeds. Mean training reward over rollout steps, for both models.](../assets/fig-treegrpo.png)

**Results.** On Terminal-Bench 2.0 (avg@5 over 89 tasks, 5 seeds):

| Model | Base | Flat GRPO | :treegrpo: |
|---|---|---|---|
| Qwen3.5-35B-A3B | 26.1±4.21 | 34.2±4.05 | **39.4±3.87** (+5.2) |
| Nemotron-3-Super-120B-A12B | 30.3±3.62 | 33.8±3.41 | **37.2±3.19** (+3.4) |

*Training performance transfer to TerminalBench 2.0, avg@5 (%); +gain is vs baseline GRPO.

> [!insight]
> :shepherd: is able to train better RL policies because mid-rollout forks turn a single outcome reward into per-step advantage, which allows better credit assignment. This adds **+5.2 points** with Qwen3.5-35B-A3B on Terminal-Bench 2.0.

# FAQ

<details markdown="1">
<summary>Does Shepherd run on Linux, macOS, and Windows?</summary>

Shepherd currently supports both Linux and MacOS. For Windows we will suggest using WSL2 for now. First-class Windows support is on the roadmap; see the [docs](https://docs.shepherd-agents.ai/) for current status.

</details>

<details markdown="1">
<summary>Do I have to rewrite my agent? Does it work with my model?</summary>

Shepherd is its own lightweight, multi-provider framework: you write agents, and meta-agents, as typed `@task` functions and swap the model behind a provider (Claude by default). A meta-agent then supervises any task on the substrate without that task knowing it is watched. It is the runtime your agents run on: you build on it directly.

</details>

<details markdown="1">
<summary>Does it replace my sandbox, or wrap it? Can I self-host?</summary>

It wraps it. Shepherd adds a layer over the container your agent already runs in, with off-the-shelf support to backends like E2B, Modal, and Daytona, behind one `Device` interface. Shepherd is open source and self-hostable, with no hosted-service lock-in.

</details>

<details markdown="1">
<summary>What does a fork capture?</summary>

Everything the agent needs to keep going from that exact point: its filesystem and process state, its message history and model context, and its position in the execution trace, all captured together in one step. Replay the branch and the agent picks up exactly where it left off.

</details>

<details markdown="1">
<summary>When you "replay" a run, do you re-run the model? Is that faithful if LLMs are non-deterministic?</summary>

A replay restores the recorded prefix byte for byte, the same messages and files, resolved against the provider's prompt cache, so it is not re-run. Only the suffix after your change re-executes. That is the point: everything up to the edit is held fixed and just the affected tail runs forward, which is what lets CRO judge an edit against an identical baseline instead of a fresh roll of the dice.

</details>

<details markdown="1">
<summary>Is this production-ready, or a research substrate?</summary>

Today Shepherd is built for research, and we are actively moving it toward production. The core is small and its correctness argument is checked in Lean, and we are maintaining the framework and hardening it with each release. You can build on it now, and it will keep getting more production-ready over time.

</details>

<details markdown="1">
<summary>Why :shepherd:? and why a sheep?</summary>

<p align="center"><img src="../assets/logo-shepherd.png" alt="Shepherd logo" height="96"></p>

A :shepherd: is exactly the job. A real shepherd doesn't do the grazing: it watches the flock, keeps the sheep on track, and steps in when one wanders toward a cliff. That is what a meta-agent does for your worker agents. It watches the run, nudges a stray back, and pulls the agent out of trouble before it falls. The logo is a sheep in a little hat, the same animal as the workers, just the one keeping an eye on the rest. And yes, we also think it's cute.

</details>

# Try it

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

📦 [**PyPI**](https://pypi.org/project/shepherd-ai/0.0.1/)  |  💻 [**Code**](https://github.com/dcx/poc-crank-v2)  |  📖 [**Docs**](https://docs.shepherd-agents.ai/)

It is the same handful of operations over a run you can fork and rewind. We are releasing Shepherd so you can build the meta-agents we have not thought of yet.

# Acknowledgments

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
