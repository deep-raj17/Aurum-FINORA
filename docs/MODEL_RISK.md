# FINORA model-risk review

Release ID: **UNASSIGNED**  
Reproducibility hash: **UNASSIGNED**  
Status: **BLOCKED — no human approval recorded**

## Required reviewer checklist

- [ ] Intended use and prohibited use are approved.
- [ ] Training and calibration datasets have licensed provenance and immutable hashes.
- [ ] No lookahead, survivorship, selection, revision, or target leakage was found.
- [ ] Baselines and all candidate models were evaluated out of sample.
- [ ] Expanding and rolling walk-forward results pass by asset class and regime.
- [ ] Interval coverage/ECE and conformal calibration pass.
- [ ] Transaction costs, turnover, liquidity and capacity are represented.
- [ ] Stress, crisis, drift, bias and sensitivity tests pass.
- [ ] Quantized artifacts remain within approved accuracy tolerances.
- [ ] Model, dataset, code and retrieval hashes reproduce the release.
- [ ] Limitations, invalidation triggers, monitoring and rollback are approved.
- [ ] Human review and financial disclaimers cannot be bypassed.

Approval must be emitted as a `HumanApproval` in a `ProductionApprovalPacket`, tied to
the exact reproducibility hash. Editing this Markdown checklist is not approval.
