---
name: new-halo-skill
description: Scaffold a new Halo skill with manifest, implementation stub, registry entry, router examples and failing tests. Use whenever a new skill is added to Halo.
---
Create a Halo skill named $ARGUMENTS, following the structure of skills/app_open/:

1. skills/$ARGUMENTS/SKILL.md with frontmatter (name, description, tools, risk: low|medium|high)
   and a short "When to use" section.
2. skills/$ARGUMENTS/skill.py implementing the Skill protocol from halo/core/contracts.py
   (`async def run(ctx, args)`), emitting step and tool events through ctx.
3. Register it in skills/registry.py; add 3 routing examples to evals/router_golden.yaml.
4. tests/skills/test_$ARGUMENTS.py with failing tests for the happy path, invalid args, and the
   policy decision for each tool it uses.
5. Run the new tests and show them failing. Don't implement the logic yet.
