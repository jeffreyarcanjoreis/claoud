---
name: find
description: "Use this skill at the very start of any new project, new session, or new user request — before writing code, running commands, or answering — to check the installed skills library and decide which skill(s), if any, best fit the task. Trigger on 'novo projeto,' 'nova sessão,' 'novo pedido,' or simply as the first step of handling any non-trivial request."
metadata:
  tags: meta, router, skill-selection
---

## Purpose

Before acting on a new project, session, or request, scan the currently installed skills (listed in the system reminder as "Available skills for use with the Skill tool") and decide which one(s) are the best match for the task at hand.

## Process

1. Read the task the user just asked for.
2. Compare it against the `description` of every installed skill (not just the name — descriptions carry the trigger conditions).
3. If one or more skills clearly match, say so explicitly before proceeding: name the skill(s) and the one-sentence reason, then invoke it/them via the Skill tool.
4. If multiple skills could apply, pick the most specific one (e.g. a project-specific skill like `kairos-voz-humana` over a generic one) rather than stacking unrelated skills.
5. If nothing installed matches, say so and proceed without a skill rather than forcing a bad fit.

## What this skill is NOT

- Not a replacement for the Skill tool itself — it's a checklist for deciding *whether and which* skill to call.
- Not meant to re-run on every single tool call within a task — apply it once per new request/topic shift, not mid-task.
- Not a substitute for reading `.agents/product-marketing.md` or similar per-skill context files — individual skills still handle their own setup steps.
