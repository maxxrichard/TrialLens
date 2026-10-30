# Contributing

## Branching

* `main` mirrors the **production** Foundry branch. Never commit to it directly.
* Feature branches `feature/<topic>` map one-to-one to Foundry branches of the same name,
  so datasets, ontology changes and app versions can be previewed in isolation.
* Every change goes through a pull request with at least one reviewer from data
  engineering; changes to markings or personal-data scope also need the DPO group.

## Local workflow

```bash
make install            # pip install -e ".[dev]"
make data               # synthetic extracts in data/raw (never use real data locally)
make run                # full pipeline + expectations report, parquet in data/out
make lint test test-e2e validate
make functions-install functions-test
```

## Rules of thumb

* **Logic lives in `triallens/logic`** as pure DataFrame functions. Foundry wrappers in
  `triallens/foundry` are generated from `pipeline_spec.py` and should not contain logic.
* **Every new column gets an expectation** if it is a key, a code with a closed
  vocabulary, or a measured value with a plausible range.
* **No silent coercion.** Unknown codes map to `UNKNOWN`/NULL and are caught by an
  expectation or a record rule, never guessed.
* **Ontology changes are additive** within a major version. Renaming or removing a
  property or changing a primary key requires a major version and a migration note.
* **Pipeline Builder boards** (`pipeline-builder/`) and their reference implementation
  in `triallens/logic` change in the same pull request.
* **Functions**: business rules in `functions-typescript/src/logic` with Jest tests;
  `src/foundry` only maps objects and performs edits.
