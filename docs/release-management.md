# Release management

## Environments and branches

| Git | Foundry branch | Purpose |
|---|---|---|
| `feature/*` | `feature/*` | development; datasets built on the branch, ontology changes in a branch preview |
| `main` | `staging` | integration build on full data, user acceptance by domain leads |
| tag `vX.Y.Z` | `master` (production) | promoted release used by the apps |

## Flow

1. **Pull request.** CI must be green: ruff, spec validation, unit tests, end-to-end
   pipeline on synthetic data (all 120 expectations, ontology contract, referential
   integrity, SQL analyses) and the TypeScript tests.
2. **Branch build in Foundry.** The same commit is built on the Foundry feature branch.
   Data expectations run on real data; failures with `on_error: FAIL` abort the build.
3. **Review.** Data engineering reviews code; markings or personal-data scope changes
   need the DPO group; ontology changes need the ontology owner.
4. **Merge → staging.** Domain leads check the affected Workshop apps on staging.
5. **Tag → production.** `release.yml` re-runs the full suite, checks the tag against
   `pyproject.toml`, builds the release bundle and publishes release notes from
   `CHANGELOG.md`. The Foundry branch is merged into `master` with the same version.

## Versioning rules

* **Major**: removed or renamed ontology properties, changed primary keys, removed
  datasets or actions. Requires a migration note and a deprecation period of one minor
  release in which both old and new properties exist.
* **Minor**: new sources, datasets, object types, properties, actions, apps.
* **Patch**: fixes without schema changes.

## Rollback

* Datasets: rebuild from the previous release tag's transforms (builds are deterministic
  given the same inputs); Foundry dataset transactions allow reverting a bad build.
* Ontology: revert the ontology branch merge; writeback data (cohorts, reviews, issue
  triage) is preserved because writeback object types are never dropped.
* Apps: Workshop versions are pinned per release and can be reverted individually.

## Environment-specific values

Marking IDs, the salt dataset RID and webhook endpoints differ between environments and
are injected at promotion time (`{{ markings.* }}` placeholders in
`triallens/foundry/step_transforms.py`); no environment-specific values are committed.
