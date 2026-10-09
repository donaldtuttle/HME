# Registration review checklist and procedure

This is a proposed registration package, not an immutable preregistration. The build authorizes no reserved-corpus run, release or merge. There is deliberately no `REGISTRATION_APPROVAL.json`.

Review the following concrete choices: synthetic relationship model; whole-patch intervention; symmetric primary preprocessing; swap budget/restarts/ties; selected vector aggregation rule and its tuning table; all six margins; all-corpus placement-achievement check; 50 independent corpora; approximate Bonferroni bootstrap; 16 MiB cap; planned descriptive conditions; costs and information access; validation observations and prior exposure.

The first validation plan is fixed in the source commit preceding tuning. FROZEN_BASELINE.json records its selection and corpus namespaces. Development and validation outputs carry source/configuration hashes and timestamps. They do not carry confirmatory authority. Validation data are exposed and cannot later become test data.

After explicit protocol approval, in a separately authorized task:

1. Resolve requested amendments before generating or inspecting any reserved test corpus. Preserve prior protocol and all validation output. Re-run correctness checks for any changed source. A new encoder or shared-feature binding needs a separately scoped experiment.
2. Set protocol status to REGISTERED only as part of approved registration preparation. Keep the frozen baseline, analysis settings, namespaces and approved scope exact.
3. Construct `experiments/meaningful_overlap_v1/REGISTRATION_APPROVAL.json` with the schema below. The approved user/reference must be verifiable; do not fabricate either. Capture the current exhaustive hash map using the supplied `source_hashes` function after all approved edits.
4. Commit the approval and exact sources. Publish this commit on a review branch before any reserved run. Record its full SHA. This action is separate from merging or releasing.
5. With separate execution authorization, use the full registration SHA and designated approval file. The evaluator checks fresh canonical GitHub branch containment, ancestry, byte equality and approval scope before creating a test RNG. Preserve remote verification evidence and run manifest.
6. Save all corpus records, failed attempts, completion records and decision output. No outcome-based seed replacement. A failure suppresses pooled analysis. Any post-exposure correction requires an amendment and explicit contamination decision. The current guard rejects an already exposed reserved namespace; adopting a fresh namespace needs reviewed source/configuration changes.

Approval schema (template only, not executable approval):

```json
{
  "status": "APPROVED",
  "protocol_id": "HME-MO-1",
  "approved_by": "REQUIRED: actual approver",
  "approval_reference": "REQUIRED: verifiable approval record",
  "approved_at_utc": "REQUIRED: actual ISO timestamp",
  "reserved_namespace": "HME-MO-1/reserved_test/000..049",
  "prior_test_exposure": false,
  "contamination_decision": "REQUIRED: explicit review finding",
  "source_sha256": {"REQUIRED": "exact source_hashes() output"}
}
```

Hash-map inspection, which does not generate data:

```bash
python -c 'import json; from experiments.meaningful_overlap_v1.integrity import source_hashes; print(json.dumps(source_hashes(), indent=2, sort_keys=True))'
```

Future command shape, **not authorized or run by this build**:

```text
python -m experiments.meaningful_overlap_v1.evaluate confirmatory
  --registration-commit FULL_APPROVED_REGISTRATION_SHA
  --approval experiments/meaningful_overlap_v1/REGISTRATION_APPROVAL.json
  --output NEW_EMPTY_RESULTS_PATH
```

Approval JSON and code guards enforce an auditable workflow, not cryptographic user authentication. Direct Python edits could bypass any local guard; they would violate the approved protocol. A proposal commit and hashes alone do not prove approval or pre-execution registration.

No canonical QOFT change, encoder redesign, performance release or production adoption is included. Production suitability requires a separately specified deployment workload even if a future accuracy gate succeeds.
