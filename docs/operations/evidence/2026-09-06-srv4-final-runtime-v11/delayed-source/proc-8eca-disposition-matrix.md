# Disposition matrix — proc_8eca51e24f34

| Finding / artifact | Classificação | Disposição | Evidência |
|---|---|---|---|
| Archive `b30eb…`, 392104728 bytes | Historical package metadata | Preservado por build/promotion receipts; archive removido depois | `proc-8eca-package-build-receipt.json`, cleanup receipt |
| Manifest `d6fad…`, 418 files | Historical source identity | Preservado; não é current authority | build/promotion receipts |
| Promotion `418/418`, bad `0` | Operational PASS | Preservado | `proc-8eca-notification.txt`, `proc-8eca-promotion-receipt.json` |
| Apply `071332` | Operational PASS | Preservado; 17/17 receipts contemporâneos ligados ao orchestrator `539594…` | messages `300332/300333`, current-state artifact |
| Runs posteriores com `source_entries=418` | Mixed historical lineage | 6 PASS, 2 FAILED; todos sem run-local seal | `proc-8eca-runs-418.json` |
| Archive local ausente | Intentional cleanup | Removido no cleanup ENOSPC; receipt checksummed | `proc-8eca-temp-cleanup-receipt.env` |
| Archive remoto ausente | Expected promotion cleanup | O próprio promoter removeu a cópia remota | promotion receipt/current state |
| Backing tree histórico | Drifted backing tree | 417/418 declarados intactos; orchestrator alterado; extras de runtime | `proc-8eca-backing-tree-validation.json` |
| Orchestrator preimage | Exact recovery component | Hash `539594…`; usado no restore drill | backing-tree/restore artifacts |
| Restore do package 418 | Reconstructible PASS | 418/418 reconstruídos; árvore temporária removida | `proc-8eca-reconstructed-restore-drill.json` |
| Successor 421 | Superseding historical source | Apply/verify `17/17 PASS`; ainda sem run-local seal | `proc-8eca-current-state.json` |
| Current 444 | Current authority | Full apply/verify com run-local seal `aa1883…` | current state/final packet |
| Current runtime | PASS | Manifest 444, repo clean, health `0/0`, setup process `0` | current state/live readback |
