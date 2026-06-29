# First real-flight runbook

This runbook turns the final launch order into a fail-closed checklist. It is a
planning artifact only: it must not be treated as approval for an autonomous Meta
launch.

## Mandatory sequence

1. CI green.
2. Docker green.
3. FinalReadiness real green.
4. Backup completed and version tagged/released.
5. One supervised test with minimum real spend.

## Minimum real spend test

- Use exactly 1 ad account.
- Use exactly 1 campaign.
- Keep a minimal daily budget and campaign cap (recommended R$6 for the first
  real Meta test, adjusted only by a human if Meta rejects the minimum).
- Keep human supervision active during the whole test window.
- Keep logs enabled before, during and after the test.
- Launch only after the kill switch has been verified.
- AI systems may recommend budget changes, but may not apply or increase budget
  by themselves.

## Financial limits

- Daily cap must be set before launch.
- Campaign cap must be set before launch and must not exceed the daily cap.
- Kill switch must be verified before launch.
- Budget increases, campaign activation and kill-switch changes are
  non-delegable human controls.

## Backup before first flight

Create and verify these artifacts before the first real-spend test:

- Database backup.
- `.env.example` backup/reference copy.
- Config backup.
- Version report.
- Git tag or release.

Recommended local command:

```bash
python scripts/create_immutable_backup.py
git tag <release-tag>
```

## Emergency plan

- Critical error: pause the campaign immediately.
- Wrong spend: disable Meta autopublish and enable the kill switch.
- Meta/API failure: return to dry-run.
- Database corruption: restore the latest verified backup immediately.
