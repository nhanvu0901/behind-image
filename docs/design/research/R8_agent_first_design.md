# R8 - Agent-first design: what credible sources say

Date of research: 2026-11-18. Every claim below rests on a page opened in this session (list in section 7).
Caveat on method: pages were read through a fetch tool that returns a model-written digest of the page, not raw HTML; wording is paraphrased from those digests. Our own measurements are not used as evidence anywhere in this file.
Strength labels: MEASURED (a number from the source, conditions stated), ARGUED (reasoned by a primary source), OPINION (author view, often vendor).

## 1. Summary: ten findings

1. Give tools the same design effort as a human UI; few, high-impact, non-overlapping tools beat wrapping every endpoint. Anthropic "Writing tools for agents" (2025-09-11). ARGUED; one example measured: concise vs detailed response 72 vs 206 tokens (Slack example).
2. Start with the simplest thing; use fixed workflows for well-defined tasks and agents only where steps cannot be predicted. Anthropic "Building effective agents" (2024-12-19, page notes some tooling advice is dated). ARGUED.
3. Tool errors should say how to fix the call; truncated or oversized results should say how to narrow. Anthropic tools post; Pinecone "Designing agent-friendly APIs" (2026-08-12). ARGUED.
4. Long jobs fit an asynchronous task model: return a task id at once, poll or get pushed status, an "input required" state for human gates, cancel, TTL. MCP spec 2025-11-25 Tasks (marked experimental); A2A spec v1.0.0 task states. ARGUED (specifications).
5. Pause/resume for humans needs persisted state keyed by a thread id, and side effects before the pause must be idempotent because the step re-runs. LangGraph interrupts docs (undated). ARGUED.
6. Progress files plus a JSON feature/status list plus git commits as checkpoints let fresh agent sessions resume; models alter JSON less than Markdown. Anthropic "Effective harnesses for long-running agents" (2025-11-26). ARGUED (no metrics reported).
7. Validate before expensive work and keep a human review gate: Shotstack (vendor) recommends offline validate, a preview step, and "human in the loop". OPINION (vendor); it reports no speed/reliability numbers.
8. CLI vs MCP: the often-quoted large token gaps come from schema loading at session start and are shrinking; one small test (Checkly, 2026-07-30) found no big difference; MCP's case rests on credentials, audit and multi-user governance. Mixed: MEASURED (small, vendor-run) plus ARGUED.
9. Multi-agent is costly and fragile for tightly coupled work: Anthropic measured about 15x tokens vs chat (multi-agent) and 4x (single agent); Cognition argues single-threaded agents are the safer default. MEASURED (Anthropic) / ARGUED (Cognition, 2025-06-12).
10. Agent reliability over repeated trials is weak in benchmarks and the principles of "agent experience" are hypotheses until measured; Microsoft measured cases where an agent-friendly change made things worse or 4-11x costlier (2026-10-06). MEASURED (small samples).

## 2. Patterns table

| Pattern | What it means | Who recommends (links) | Strength | Fits when | Does not fit when |
|---|---|---|---|---|---|
| API-first / headless core, human page is one client | Agent and UI call the same operations; docs and schema as ground truth | Shotstack says agent and Studio share one JSON format (https://shotstack.io/learn/agentic-video-editing-best-practices/); Pinecone checklist (https://www.pinecone.io/blog/designing-agent-friendly-apis/); Microsoft AX post (https://developer.microsoft.com/blog/what-is-agent-experience-ax/) | ARGUED / OPINION. No source found that measures "API-first" itself | Operations already exist as routes | Routes return huge or untyped payloads (needs trimming) |
| CLI as agent interface | Agent runs commands; output structured; help text discoverable | Nx (2026-03-05): detect agent context, emit JSON, idempotent re-run, keep the CLI surface (https://nx.dev/blog/making-nx-agent-ready); Anthropic skills post: scripts agent runs without loading them (https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | ARGUED. Microsoft MEASURED: telling agent to use a CLI raised passed checks 30/80 to 75/80 (SPFx upgrade, Sonnet 4.6, 5 runs) | Coding agent in a terminal, local files | Many users with separate credentials (see section 4) |
| MCP server / tools | Typed tools with inputSchema, optional outputSchema, isError results, discovery via tools/list | MCP spec 2025-06-18 (https://modelcontextprotocol.io/specification/2025-06-18/server/tools); OpenAI function calling guide (https://developers.openai.com/api/docs/guides/function-calling) | ARGUED (spec) | Non-terminal clients, governed remote access | Local-only use where CLI exists; many tools bloat context |
| File/artifact contracts between stages, workspace per run | Stage reads/writes named files with fixed shapes; progress file; feature list JSON | Anthropic harness post (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); 12-factor agents: unify execution and business state (https://github.com/humanlayer/12-factor-agents, undated, author Dex Horthy) | ARGUED | Multi-session, resumable work | Tight interactive edits needing sub-minute feedback (no source addresses this) |
| Small typed operations vs free file editing | Schema-validated calls (enums, strict mode) rather than arbitrary edits | OpenAI: use enums/structure to make invalid states unrepresentable; "always enable strict mode" (function calling guide); Anthropic structured outputs (https://platform.claude.com/docs/en/build-with-claude/structured-outputs); OWASP LLM06 warns against open-ended extensions such as arbitrary shell (https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | ARGUED | Predictable edits, safety needed | Open-ended creative work; schemas lack recursion/numeric limits in Anthropic's structured outputs |
| "State and next actions" answer | Command returns status plus suggested next steps as JSON | Nx emits "completion with suggested next steps"; MCP Tasks carry status, statusMessage, pollInterval | ARGUED. No measurement found | Multi-stage pipelines | none found |
| Idempotent, resumable commands | Retried mutation is a no-op; re-invocation does not redo work | Pinecone ("agents retry by default"); Nx; LangGraph interrupts docs (https://docs.langchain.com/oss/python/langgraph/interrupts); A2A push notifications are at-least-once, handle duplicates idempotently (https://raw.githubusercontent.com/a2aproject/A2A/main/docs/specification.md) | ARGUED | Retries, long jobs | none found |
| Structured, recoverable errors | What was wrong, concrete fix, stable code (RFC 9457 shape suggested) | Anthropic tools post; Pinecone; Anthropic multi-agent post says tell the agent when a tool fails so it adapts (https://www.anthropic.com/engineering/multi-agent-research-system); 12-factor: compact errors into context | ARGUED | Always | none found |
| Validate / dry-run / preview | Lint without side effects; preview before render | Shotstack (offline validate, studio preview); Comfy local MCP has validate_workflow (https://docs.comfy.org/agent-tools/mcp); Pinecone (dry-run, reversibility) | OPINION/ARGUED | Costly final step (render) | Validator weaker than the real consumer (Shotstack notes MCP/API lack the lint) |
| Human gates and interrupts | Pause for approval, resume with same thread/task | LangGraph; A2A INPUT_REQUIRED; MCP says there SHOULD be a human able to deny tool calls; OpenAI practical guide: plan for human intervention, risk-rate tools low/medium/high (https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf, date inferred 2025) | ARGUED | Irreversible or high-impact actions | Every action: approval fatigue (section 4) |
| Checkpoints, undo, audit log | Git commits, persisted graph state, logged tool use | Anthropic harness post; LangGraph checkpointer (in-memory lost on restart; DB recommended); MCP spec: clients SHOULD log tool usage for audit | ARGUED | Long runs | none found |
| Docs for agents (AGENTS.md, skills, llms.txt) | Plain-text instructions, progressive disclosure, markdown pages | AGENTS.md (https://agents.md/; claims 60k+ projects, own claim); llms.txt (Jeremy Howard, 2024-09-03, https://llmstxt.org/); Agent Skills; Remotion ships skills (https://www.remotion.dev/docs/ai/skills) | ARGUED. MEASURED: Microsoft docs tip naming the failing approach led to tool use 5/5 vs 1/5 for a direct tip | Agents lack domain knowledge | Large skill files cost tokens (a 12,755-token SKILL.md in PubNub's test) |
| Agent-computer interface (ACI) | Interface designed for LM limits (compact commands, feedback) | SWE-agent paper (https://arxiv.org/abs/2405.15793, 2024-05) | ARGUED; 12.5% pass@1 SWE-bench reported, no ablation number on that page | Code/file tasks | Older evidence (2024) |
| Tool design guidance | Prefix naming, response_format, pagination, fewer than ~20 tools | Anthropic tools post; OpenAI (<20 tools "soft suggestion"; practical guide: >15 distinct tools OK for some, <10 overlapping fail for others) | ARGUED | Always | none found |
| Evaluation of agent runs | Realistic multi-step tasks, track accuracy, runtime, tool calls, tokens, errors; read transcripts | Anthropic tools post; tau-bench (https://arxiv.org/abs/2406.12045) pass^k; Google ADK has evaluation incl. user simulation (https://adk.dev/) | ARGUED; MEASURED in tau-bench (section 4) | Before and after any change | none found |

## 3. Examples table

| Project | Agent interface | Where a human approves | Speed / reliability reported | Link |
|---|---|---|---|---|
| Remotion + coding agents | Agent writes React/TS code; slash-command skills (create, render, captions, studio, docs) | Not stated; Studio preview exists | Page claims none (no speed or reliability statement) | https://www.remotion.dev/docs/ai/skills |
| Shotstack | Declarative JSON "edit"; API, CLI (validate, studio), MCP server (beta per search snippet, not opened) | Recommended: human reviews template, preview before render | No measured numbers; says failed renders not billed (vendor, 2026-08-12) | https://shotstack.io/learn/agentic-video-editing-best-practices/ |
| JSON2Video | JSON movie; MCP lets agent "write, validate and render" | Not stated | No render times or uptime; async job id then poll/webhook (vendor, 2026-10-18) | https://json2video.com/how-to/video-editing-api/ |
| Blender MCP (ahujasid) | 9 tools incl. execute_blender_code over a JSON/TCP socket to an addon | User must save work first; optional safe mode blocks risky scripts | None quantified; README says connections may fail first try, requests time out, split complex steps; socket has no auth | https://github.com/ahujasid/blender-mcp |
| ComfyUI (official MCP) | Discover templates/nodes, run_template or submit_workflow, wait_for_job, get_output; local validate_workflow | Few controls described | "Early release"; complex workflows may need retries; no numbers | https://docs.comfy.org/agent-tools/mcp |
| Descript (Underlord via MCP) | Natural-language edits from Claude/ChatGPT/any MCP client; also API, CLI | Optional: open Descript to review; can track and cancel a job | No measured numbers; a testimonial of "one-quarter the time" (anecdote) | https://www.descript.com/mcp |

Not verified from a primary page, hence excluded: DaVinci Resolve MCP, ffmpeg MCP, Figma MCP, Editly, Creatomate (only directory listings or search snippets seen), open-source short-video generators (not searched in depth).

## 4. Disagreements, warnings, counter-evidence

**MCP vs CLI vs HTTP.**
- For CLI: PubNub/Blocks (2026-08-28, vendor) measured schema tokens at start with count_tokens on claude-sonnet-4: filesystem MCP 14 tools = 2,614; GitHub MCP 44 tools = 14,243; 85 tools = 26,644; CLI = 0. Link https://www.pubnub.com/blog/mcp-vs-cli-context-window-cost-blocks-ai. Stacklok (2026, vendor) cites a Scalekit benchmark of $3.20 vs $55.20 per 10,000 GitHub operations (secondhand; Scalekit page not opened): https://stacklok.com/blog/mcp-vs-cli-tools-why-security-changes-the-answer/.
- Against the gap: Checkly (2026-07-30, vendor, one task, 3 runs): MCP about 48-50k context tokens vs CLI 45-48k; harnesses now defer MCP tool loading. Link https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/.
- Governance: Stacklok argues CLI agents inherit the invoker's credentials, MCP keeps credentials server-side with per-user auth and audit; recommends skills for knowledge, CLI for local dev tools, MCP for remote multi-user. OPINION (vendor sells MCP governance).
- Code over tool calls: Anthropic (2025-11-04) reports one example dropping 150,000 to 2,000 tokens by code execution over MCP, not a general benchmark, and notes sandboxing overhead: https://www.anthropic.com/engineering/code-execution-with-mcp. Cloudflare "Code Mode" (2025-09-26) gives no benchmark: https://blog.cloudflare.com/code-mode/.
- Raw HTTP vs SDK: Pinecone cold trials (Sonnet 5, 3 runs): raw REST reached first success in 3 turns; SDK agents spent nearly half their turns learning signatures from TypeErrors. Tiny sample, vendor.

**Many small tools vs few high-level.** Anthropic: few, consolidated, non-overlapping (e.g. one scheduling tool). OpenAI: under ~20 tools; practical guide says the problem is similarity, not count. Both agree on overlap as the harm. No source measured the best count.

**Free file editing vs validated operations.** OWASP LLM06 mitigation: avoid open-ended extensions like arbitrary shell, minimal permissions. Anthropic harness post: restrict agents to changing only a `passes` field in a JSON list. Counter-direction: Anthropic code-execution post argues code gives flexibility, at the price of sandboxing. No source compared the two on the same task.

**One agent vs several.** OpenAI practical guide: maximize a single agent first, split when instructions or tool selection fail. Cognition (2025-06-12): parallel subagents make conflicting assumptions; share full traces. Anthropic: multi-agent beat single-agent Opus 4 by 90.2% on its internal research eval but with about 15x chat tokens, and is a poor fit for tasks sharing one context or with many dependencies (most coding).

**Where a human gate is worth its cost.** MCP spec and OpenAI guide: gate high-risk, irreversible actions. Anthropic sandboxing post (2025-10-20): constant prompts cause approval fatigue; sandbox boundaries cut prompts by 84% in internal use (method not described). Shotstack recommends human review before render. Descript makes review optional. No source measured the optimal gate placement.

**Cost and latency of agentic loops.** Anthropic: agents about 4x chat tokens. Pinecone: cold agent, about 90 s and about $0.30 per run for a first API session. Microsoft: Sonnet 5 cost 3.7x more per run than Sonnet 4.6 on SPFx upgrades (3 scenarios, 15 runs each) despite lower token price.

**Security.** OWASP LLM06 (2025): excessive functionality, permissions, autonomy; require human approval for high-impact actions, enforce authorization downstream. Anthropic computer-use docs: use a VM, allowlist domains, keep credentials away, human-confirm consequential actions; model may follow instructions found in pages or images. MCP spec: servers MUST validate inputs and rate limit; annotations from untrusted servers are untrusted. Blender MCP README: socket has no authentication.

**Counter-evidence: agent-first may not pay off, or fails in practice.**
- tau-bench paper (2024-06): top function-calling agents succeeded on under 50% of tasks and pass^8 was under 25% in retail. MEASURED but old (2024) and about conversational customer tasks. https://arxiv.org/abs/2406.12045
- Microsoft (2026-10-06): "best practices are hypotheses until you measure them"; JSON-input CLI mode made one small model get 2 of 5 deployments right and cost 4x-11x more; the context7 MCP server gave no lift because its tools failed to load in 3 of 5 runs. MEASURED, small samples. https://developer.microsoft.com/blog/what-is-agent-experience-ax/
- Nx does "detect agent context, adapt output, don't rebuild the CLI surface" - an argument for modest adaptation over redesign (ARGUED, no results reported).
- "Give the agent the same UI via computer use": Anthropic docs state each screenshot costs about 1,000-1,800 input tokens, clicks can miss, the model may act as if a step succeeded without checking, and pruning screenshots breaks prompt caching. ARGUED/documented limits; the page presents it as a fallback, not an alternative to APIs. https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
- Anthropic itself: prefer simple workflows over agents when steps are predictable.
- Tool sprawl: only secondhand token figures above; no source measured accuracy loss as tool count grows (OpenAI says "soft suggestion").
- Compounding-error arithmetic (e.g. 95% per step giving about 36% over 20 steps) appeared only in a search snippet of an opinion article; not opened, not relied on.

## 5. Speed: what is recommended, with measured numbers only

| Technique | Source | Measured number and conditions |
|---|---|---|
| Fewer output tokens, smaller/faster model, fewer requests, parallelize, stream progress, do not call an LLM when code knows the answer | OpenAI latency guide (https://developers.openai.com/api/docs/guides/latency-optimization) | No measured number found (page gives no speedups) |
| Single structured call with schema | Anthropic and OpenAI structured outputs docs | Guarantees valid, schema-conforming JSON. First request with a new schema is slower (grammar compile); Anthropic caches compiled grammars 24 h. No latency number found. Anthropic: unsupported numeric/length constraints and recursion |
| Prompt caching | Anthropic docs (https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | Pricing, not latency: cache read 0.1x base input (0.05x on listed newest models), 5-min write 1.25x, 1-h write 2x; default lifetime 5 minutes; minimum 512-4,096 tokens by model. Latency: no measured number found (qualitative only) |
| Concise tool responses | Anthropic tools post | Concise 72 tokens vs detailed 206 in one Slack example |
| Small payloads / deferred tool loading | Anthropic code-execution post; PubNub | 150,000 to 2,000 tokens in one example; schema tokens 2,614-26,644 for the MCP servers listed (section 4) |
| Parallel subagents | Anthropic multi-agent post | Up to 90% less time on complex research queries; at about 15x tokens |
| Better tool descriptions | Anthropic multi-agent post | 40% shorter task completion time for later agents after a tool-testing agent rewrote descriptions |
| Routing easy requests to a fast path, hard to an agentic path | OpenAI: "don't default to an LLM"; Anthropic: workflows vs agents | No measured number found for routing itself |
| Async task + progress | MCP Tasks (pollInterval, progress notifications), A2A streaming/push | Specifications; no latency numbers |
| Agent latency in practice | Pinecone | About 90 s and $0.30 per cold run (Sonnet 5, 3 runs, bare harness): a data point, not a target |
| Tool-call failure rates | Only in search snippet (3-15%), not opened | Not used |

## 6. Applicability notes (neutral)

1. Choose artwork (library/dossier): read-heavy; fits typed query tools, pagination, concise vs detailed responses, resolved names rather than ids. Needs: stable search/list operations and a dossier schema.
2. Script (outline, narration): single structured call with a schema fits (structured outputs); human gates map to interrupt/input-required; needs approval state stored and resumable.
3. Voice (tens of minutes): matches async task pattern (task id, poll interval, status message, cancel, TTL; idempotent restart). Needs: job resource with progress and resumable synthesis.
4. Picks: choice among candidates with images/clips; fits typed operations (list candidates, set pick, validate coverage) and a risk-rated gate; response size matters because of images. Needs: compact candidate listing and per-part undo.
5. Storyboard: declarative JSON plus a checker already resembles Shotstack/JSON2Video validate-then-render and the "validated operations vs file edit" question; fits schema-constrained small edits, a validate/dry-run command, a preview step. Needs: operation-level edit API or patch format, validator returning fix-oriented errors.
6. Export (render/mux): costly, mostly mechanical; fits validate-first, async job, idempotent re-run, audit log. Needs: pre-render lint and frame-level checks (Shotstack suggests poster frame check).
Across stages: a state-and-next-actions endpoint, workspace-per-run files, AGENTS.md or skills for outside agents, structured errors, audit log of agent actions, and an evaluation set of tasks with pass^k tracking would each have to exist; no source says which matter most.

## 7. Sources

Opened and used (URL | publisher/author | date | kind):
1. https://www.anthropic.com/engineering/building-effective-agents | Anthropic | 2024-12-19 | engineering write-up
2. https://www.anthropic.com/engineering/writing-tools-for-agents | Anthropic | 2025-09-11 | engineering write-up
3. https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | Anthropic | 2025-10-16 | engineering write-up
4. https://www.anthropic.com/engineering/code-execution-with-mcp | Anthropic | 2025-11-04 | engineering write-up
5. https://www.anthropic.com/engineering/multi-agent-research-system | Anthropic | 2025-06-13 | engineering write-up
6. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | Anthropic | 2025-11-26 | engineering write-up
7. https://www.anthropic.com/engineering/claude-code-sandboxing | Anthropic | 2025-10-20 | engineering write-up
8. https://platform.claude.com/docs/en/build-with-claude/prompt-caching | Anthropic | undated | official docs
9. https://platform.claude.com/docs/en/build-with-claude/structured-outputs | Anthropic | undated | official docs
10. https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool | Anthropic | undated | official docs
11. https://modelcontextprotocol.io/specification/2025-06-18/server/tools | MCP project | version 2025-06-18 | specification
12. https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks | MCP project | version 2025-11-25 (experimental) | specification
13. https://raw.githubusercontent.com/a2aproject/A2A/main/docs/specification.md | A2A project | v1.0.0, undated; first 100k of 157k chars read | specification
14. https://docs.langchain.com/oss/python/langgraph/interrupts | LangChain | undated | official docs
15. https://docs.langchain.com/oss/python/langgraph/durable-execution | LangChain | undated | official docs (page covers checkpoints only, not durable-execution semantics)
16. https://developers.openai.com/api/docs/guides/function-calling | OpenAI | undated | official docs
17. https://developers.openai.com/api/docs/guides/structured-outputs | OpenAI | undated | official docs (first 100k chars)
18. https://developers.openai.com/api/docs/guides/latency-optimization | OpenAI | undated | official docs
19. https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf | OpenAI | undated, date inferred 2025 | vendor guide (read by extracting PDF text locally)
20. https://adk.dev/ | Google | undated | official docs (landing page only)
21. https://github.com/humanlayer/12-factor-agents | Dex Horthy / HumanLayer | undated (date inferred 2025) | community post (factor titles only)
22. https://arxiv.org/abs/2405.15793 | Yang et al. (SWE-agent) | 2024-05-06, rev. 2024-11-11 | paper (abstract)
23. https://arxiv.org/abs/2406.12045 | Yao et al. (tau-bench) | 2024-06-17 | paper (abstract)
24. https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ | OWASP | 2025 edition | project documentation
25. https://llmstxt.org/ | Jeremy Howard | 2024-09-03 (modified 2026-08-10) | community proposal
26. https://agents.md/ | AGENTS.md project (Linux Foundation stewardship stated) | undated | community specification
27. https://cognition.com/blog/dont-build-multi-agents | Walden Yan, Cognition | 2025-06-12 | engineering opinion
28. https://developer.microsoft.com/blog/what-is-agent-experience-ax/ | Waldek Mastykarz, Microsoft | 2026-10-06 | engineering write-up
29. https://nx.dev/blog/making-nx-agent-ready | Nx | 2026-03-05 | vendor engineering blog
30. https://www.pinecone.io/blog/designing-agent-friendly-apis/ | Joerg Schad, Pinecone | 2026-08-12 | vendor engineering blog
31. https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/ | Stefan Judis, Checkly | 2026-07-30 | vendor blog
32. https://www.pubnub.com/blog/mcp-vs-cli-context-window-cost-blocks-ai | Markus Kohler, PubNub | 2026-08-28 | vendor blog
33. https://stacklok.com/blog/mcp-vs-cli-tools-why-security-changes-the-answer/ | Stacklok | modified 2026-04-29 | vendor blog
34. https://blog.cloudflare.com/code-mode/ | Cloudflare (Varda, Pai) | 2025-09-26 | vendor blog
35. https://shotstack.io/learn/agentic-video-editing-best-practices/ | Derk Zomer, Shotstack | 2026-08-12 (upd. 2026-09-11) | vendor marketing
36. https://json2video.com/how-to/video-editing-api/ | JSON2Video | 2026-10-18 | vendor marketing
37. https://www.remotion.dev/docs/ai/skills | Remotion | undated | official docs
38. https://github.com/ahujasid/blender-mcp | ahujasid (community) | undated | open-source README
39. https://docs.comfy.org/agent-tools/mcp | Comfy | undated | official docs
40. https://www.descript.com/mcp | Descript | undated | vendor page

Tried, could not use:
- https://google.github.io/A2A/ (HTTP 404).
- https://github.com/a2aproject/A2A/blob/main/docs/specification.md (only GitHub navigation returned; the raw file was used instead).
- https://owasp.org/www-project-top-10-for-large-language-model-applications/ (opened but contained no list; replaced by source 24).
- Seen only as search results, never opened, so not cited as evidence: Scalekit benchmark, Sideko Stripe benchmark, apideck, Speakeasy and other AX posts, Shotstack MCP overview page, Creatomate pages, DaVinci Resolve and ffmpeg MCP listings, Editly (no results), tianpan/hackernoon/atla reliability posts.

Points with no trustworthy evidence found: measured latency gain from prompt caching or structured output; measured benefit of an API-first redesign as such; best tool count; routing fast path vs agentic path; optimal human-gate placement; any speed/reliability number for agent-driven video editing from a primary page.
