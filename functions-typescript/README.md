# TrialLens Functions (TypeScript)

Foundry Functions used by the Workshop apps, the action types and the AIP Logic flows.

```
src/logic/     pure TypeScript business rules (no Foundry dependency) - unit tested in CI
src/foundry/   Foundry bindings: @Function / @OntologyEditFunction classes that map
               ontology objects to the logic types and perform ontology edits
test/          Jest tests for src/logic
```

| Function | Used by |
|---|---|
| `CohortFunctions.previewCohortSize`, `cohortFunnel`, `cohortSummary` | Cohort Builder |
| `CohortFunctions.createCohortFromCriteria` | action `createCohort` |
| `CohortFunctions.addPatientsToCohort`, `removePatientFromCohort` | actions of the same name |
| `BiomarkerReviewFunctions.suggestBiomarkerReview`, `assayRunReviewQueue` | Biomarker Review |
| `BiomarkerReviewFunctions.reviewBiomarkerMeasurement` | action `reviewBiomarkerMeasurement` |
| `DataQualityFunctions.issuePriority`, `triagedIssueIds` | Data Quality dashboard |
| `DataQualityFunctions.updateDataQualityIssue` | action `updateDataQualityIssue` |
| `AipTools.*` | AIP Logic flows in `aip-logic/` |

## Local development

```bash
npm install
npm run lint   # type-check src/logic and tests
npm test       # jest
```

`src/foundry` depends on `@foundry/functions-api` and the generated `@foundry/ontology-api`,
which only exist in the Foundry Functions repository, so it is compiled there
(`tsconfig.foundry.json`) and not in GitHub CI. Keeping every rule in `src/logic` is what
makes the behaviour testable outside Foundry.

Property names follow the ontology convention: the dataset column `latest_ptau217`
becomes the property API name `latestPtau217`.
