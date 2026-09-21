# Daily logs (Aziz / Naved)

Shared templates and Cursor skill for HyrePath HQ **Daily Logs**.

## Invoke (Cursor)

With Notion MCP connected and this repo open on branch `product-doors/baseline`:

```text
Close out today for Aziz
Close out today for Naved
Log Aziz daily from @docs/daily/aziz-TEMPLATE.md
Update HyrePath HQ for Naved — use PR <url>
```

The skill `.cursor/skills/hyrepath-daily-log/` will gather plan + PR + git, run the claim-honesty reviewer (`.cursor/agents/daily-log-reviewer.md`), then create/update one Daily Log row.

## Templates

- [aziz-TEMPLATE.md](aziz-TEMPLATE.md) — copy to `aziz-YYYY-MM-DD.md` or fill in place
- [naved-TEMPLATE.md](naved-TEMPLATE.md) — same for Naved

Incomplete checklists are fine: the agent can derive Completed / Left from PR and implementation when evidence exists.

## Destination

- HQ: https://app.notion.com/p/3ced886b9260817ea3fde2b8db82ba4a
- Daily Logs: https://app.notion.com/p/8c0b9bd9f03e438f851d0a36610f1add
- Body format example: https://app.notion.com/p/3d0d886b926081b681e7c13502ee60e6

## Notion Skill

Mirror workflow as a Notion Skill under HyrePath HQ (created via Notion MCP). After creation, paste the skill URL here:

- Notion Skill URL: https://app.notion.com/p/3d1d886b9260812a947cf53fb4c5a1c5
