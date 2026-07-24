# Phase 54 provenance and approval lineage

The old local Phase 52 artifacts remain byte-preserved under `legacy-phase52/`. They prove historical work only.

## Non-reuse rule

`APROVADO: phase52-wave0` and `APROVADO: phase52-wave1` do not authorize Phase 54 writes. Plan 02 may cite them only after recording:

- exact legacy SHA-256;
- current live input SHA-256;
- scope comparison;
- original expiry and typed-confirmation text;
- anti-drift readback;
- verdict `historical_only` or `same_scope_fresh`.

Any missing field, changed target, expired timestamp or drift yields `historical_only` and requires a new Phase 54 typed confirmation.

## External builder lineage

The `oci-admin` backend is external. Plan 03 requires its owner to provide a commit/receipt that is independently read back and hash-validated. The builder output must include exactly the 10.31 VCN/subnet/private-IP targets and no 10.21 target. Preparing a local document or editing this repo cannot satisfy that gate.

## Immutable legacy hashes

| File | SHA-256 |
|---|---|
| `52-01-EVIDENCE.json` | `55d4b460ab011eaa5bcdf9488a1971610fefbeacda4bbdc542386222741e3ed8` |
| `52-01-EVIDENCE.md` | `955d73a7a1ca4990cd6e4420e44a38adb3b5fb1fd7ea3b288b5277798e473b0d` |
| `52-01-GATE.json` | `36e143e9d11317f7bfdb79a620f1c53ac19bd033e97bd36465e71fb0acd8a8f5` |
| `52-02-EVIDENCE.json` | `3c1231794c1bd68c428ef0f6a187df1113ba61fe56697307178b1066a18e2b50` |
| `52-02-EVIDENCE.md` | `60ef2b509ec809ad20f66e5b6243b8ef01480019cfff7d68055216d16a0c4a5c` |
| `52-02-GATE.json` | `c34cc179861f9a5b53c60d5e9c5416a5d907ff98230ef2797fd024f100b03041` |
| `rollback-receipt.json` | `bd7fc332c671caf6b01fb871c3fd7615334d1dd4ce402ac4f8696d55d4ca584e` |
