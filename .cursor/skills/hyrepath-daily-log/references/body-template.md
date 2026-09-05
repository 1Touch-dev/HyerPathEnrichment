# Daily Log page body template

Do not put the page title in the body (Notion shows `Name` as the title).

```markdown
## Today's tasks
### {Workstream name}
- [x] done item with evidence
- [ ] left item

### {Optional second workstream}
- [ ] …

## Evidence
**Git branch**
- [branch-name](https://github.com/1Touch-dev/HyerPathEnrichment/tree/branch-name) — summary of commits/files if known

**PR**
- [PR title](https://github.com/1Touch-dev/HyerPathEnrichment/pull/N) — checks status if known

**Commits / artifacts**
- [`abc1234`](https://github.com/1Touch-dev/HyerPathEnrichment/commit/abc1234) — short description
- Links to ADRs, audits, or docs when relevant

## End of day
Status = **{Status}** ({done}/{total}). {One or two sentences: what closed, what is left, why / blocker. PR field note if empty.}
```

Mirror structure and tone of the golden example page (see `notion-ids.md`).
