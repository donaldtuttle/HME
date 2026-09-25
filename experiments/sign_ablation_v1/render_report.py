"""Render HME-NN-2A's saved observations; does not execute evaluation seeds."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
result = json.loads((HERE/'results/results.json').read_text())
for filename, expected in result['raw_files'].items():
    assert hashlib.sha256((HERE/'results'/filename).read_bytes()).hexdigest() == expected
runs = [json.loads((HERE/'results'/f'seed_{seed}.json').read_text()) for seed in result['completed_seeds']]
a = result['analysis']
p = a['primary']
primary = next(c for c in a['conditions'] if c['query_mode']=='native' and c['noise_sigma']==1.)
labels = {'hme_abs':'Current HME (absolute)', 'hme_signed':'Experimental HME (signed)', 'nn_cosine':'Signed cosine NN'}


def estimate(stat, percent=False, level=95):
    scale,digits = (100,2) if percent else (1,3)
    lo,hi = stat[f'ci{level}']
    return f"{scale*stat['mean']:.{digits}f} [{scale*lo:.{digits}f}, {scale*hi:.{digits}f}]"


def supported(value):
    return 'supported' if value else 'not established'


flags = p['decisions']
lines = ['# HME-NN-2A: sign ablation with retained field bias', '',
    f"Registration: [`{result['registration_commit'][:7]}`]({result['registration_url']}). "
    'The protocol, variant, evaluator and correctness fixtures were public before evaluation.', '',
    f"Execution: {result['started_at_utc']} through {result['finished_at_utc']}. "
    f"All {len(runs)} registered seeds completed; protocol deviations: {len(result['deviations'])}.", '',
    '## Primary result', '',
    f"**Equivalence within plus or minus one percentage point: {supported(flags['equivalence_within_margin'])}.** "
    f"Noninferiority within one point: **{supported(flags['noninferiority_within_margin'])}**.", '',
    'The primary condition is native query preprocessing, Gaussian noise sigma 1.0, '
    '128 items of dimension 16 at a shared position. Accuracy is averaged across thirty independent seeds.', '',
    '| Arm | Top-1 accuracy, percent [95% seed-bootstrap interval] |', '|---|---:|']
for name in labels:
    lines.append(f"| {labels[name]} | {estimate(primary['arms'][name]['top1_accuracy'],True)} |")
lines += ['', '| Paired contrast | Difference, percentage points [95% interval] |', '|---|---:|']
for left,right in result['protocol']['secondary']['contrasts']:
    lines.append(f"| {labels[left]} minus {labels[right]} | {estimate(primary['contrasts'][f'{left}_minus_{right}']['top1_accuracy'],True)} |")
lines += ['', f"The primary signed-HME-minus-NN **90% interval** is "
          f"**[{100*p['paired_delta']['ci90'][0]:.2f}, {100*p['paired_delta']['ci90'][1]:.2f}] percentage points**. "
          'Equivalence requires this entire interval to lie strictly inside [-1, +1] points; '
          'noninferiority requires its lower endpoint to exceed -1 point. A nonsignificant '
          'difference or an interval overlapping zero does not establish equivalence.', '',
          f"A deficit exceeding the one-point margin is {supported(flags['deficit_exceeds_margin'])}. "
          f"Lower mean signed-HME accuracy under the 95% effect interval is {supported(flags['lower_mean_accuracy_ci95'])}; "
          f"higher mean accuracy is {supported(flags['higher_mean_accuracy_ci95'])}.", '',
          'These decisions use the preregistered approximate percentile-bootstrap procedure: '
          '50,000 resamples of thirty paired seed-level metrics. Queries sharing a field are not '
          'treated as independent replicates. No guaranteed power or exact finite-sample type-I '
          'error control is claimed. The sample size and one-point margin were not changed.', '',
          'The sign intervention removes the observed primary mean deficit, but the '
          'registered equivalence hypothesis remains unresolved: the upper endpoint '
          'exceeds the positive margin. The result permits a benefit larger than one '
          'point; it does not establish such a benefit. It also does not establish '
          'superiority under the separate registered 95% effect-interval criterion.', '',
          'The secondary symmetric-preprocessing, sigma 1.0 condition favors NN: '
          f"signed HME minus NN is {estimate(next(c for c in a['conditions'] if c['query_mode']=='symmetric' and c['noise_sigma']==1.)['contrasts']['hme_signed_minus_nn_cosine']['top1_accuracy'],True)} "
          'percentage points (descriptive 95% interval). The primary outcome should '
          'not be generalized to every preprocessing condition.', '',
          '## What changed', '',
          'The experimental variant replaces only `abs(vdot(payload, query))` with '
          '`real(vdot(payload, query))`. It retains the field bias, 0.38/0.42/0.20 weights, '
          'clipping, thresholds, preprocessing, decoded outputs and storage behavior. '
          'The generated source is pinned and hashed. The public package still uses the '
          'original default engine; this report does not promote the experimental variant.', '',
          'Signed NN retains copies of the same processed vectors, artifact records and lineage. '
          'Every arm has identical queries and side information and a common 4 MiB maximum '
          'persistent-storage budget. All arms fit. This tests the sign intervention with the '
          'existing prior retained; it does not test a query-dependent field readout.', '',
          '## All registered conditions', '',
          'Only native sigma 1.0 has a confirmatory equivalence decision. Other cells and contrasts '
          'are descriptive, with no multiplicity correction or substitution for the primary. '
          'Zero-width intervals describe these observations, not population certainty.', '']
for metric,title,percent in [('top1_accuracy','Top-1 accuracy (%)',True),
                              ('top5_accuracy','Top-5 accuracy (%)',True),
                              ('mean_reciprocal_rank','Mean reciprocal rank',False)]:
    lines += [f'### {title}', '', '| Query mode | Noise sigma | Current HME | Signed HME | Signed NN |',
              '|---|---:|---:|---:|---:|']
    for c in a['conditions']:
        values = [estimate(c['arms'][name][metric],percent) for name in labels]
        lines.append(f"| {c['query_mode']} | {c['noise_sigma']:g} | " + ' | '.join(values) + ' |')
    lines += ['']
lines += ['## Primary observations by seed', '',
          '| Seed | Current HME correct / 128 | Signed HME correct / 128 | Signed NN correct / 128 |',
          '|---:|---:|---:|---:|']
for run in runs:
    c = next(c for c in run['cells'] if c['query_mode']=='native' and c['noise_sigma']==1.)
    counts = [sum(rank==1 for rank in c['arms'][name]['target_ranks']) for name in labels]
    lines.append(f"| {run['seed']} | " + ' | '.join(map(str,counts)) + ' |')
lines += ['', '## Newly measured costs', '',
          '| Arm | Median persistent bytes | Maximum persistent bytes | Numeric array bytes | Median API query (ms) | Median seed p95 (ms) | Median paired latency / NN |',
          '|---|---:|---:|---:|---:|---:|---:|']
for name in labels:
    s,t = a['storage'][name],a['latency'][name]
    assert len(set(s['numeric_array_bytes']))==1
    lines.append(f"| {labels[name]} | {s['median_persistent_bytes']:,.0f} | {s['max_persistent_bytes']:,} | "
                 f"{s['numeric_array_bytes'][0]:,} | {t['median_of_seed_medians_ns']/1e6:.4f} | "
                 f"{t['median_of_seed_p95_ns']/1e6:.4f} | {t['median_paired_ratio_to_nn']:.1f} |")
lines += ['', 'Storage is recursive CPython object/owned-array accounting, including field, cached '
          'patterns, records and lineage, with aliases counted once. Interpreter/shared code, '
          'allocator overhead and temporary query buffers are excluded. This is a common maximum '
          'budget at equal task size, not an equal-consumed-byte capacity frontier.', '',
          'Latency uses 32 primary-condition queries per seed, four warmups per arm, three repetitions, '
          'rotating arm order, top-k 5, and one numerical-library thread. Both HME variants also '
          'construct decoded outputs; NN returns rankings/scores. Shared-host timings describe '
          'these public implementations, not intrinsic algorithmic lower bounds. The sign variant '
          'retains the original execution path, including its per-candidate operations.', '',
          '## Unmatched-query acceptance', '',
          '| Arm | Accepted / total, both query modes |', '|---|---:|']
for name in labels:
    values = [r['unmatched_queries'][mode][name] for r in runs for mode in ('native','symmetric')]
    lines.append(f"| {labels[name]} | {sum(v['accepted'] for v in values)} / {sum(v['total'] for v in values)} |")
lines += ['', 'These are fresh Gaussian vectors with no designated stored target. Acceptance at '
          'default policies is not calibrated correctness or out-of-distribution detection. '
          'Raw scores are not used as probabilities.', '',
          '## Scope and reproduction', '',
          'This is a new, independent sign-ablation experiment on synthetic vectors at one load '
          'and dimension. It does not replace the [HME-NN-1 evidence](../nn_baseline_v1/REPORT.md), '
          'test candidate-specific field retrieval or change encoding. '
          '[Stage 2 requirements](../../docs/FIELD_RETRIEVAL_DESIGN.md) explain the separate '
          'addressing, overlap, polarity and cost controls still needed.', '',
          f"Environment: Python {result['environment']['python']}, NumPy {result['environment']['numpy']}. "
          'Exact source/generated-module hashes, data hashes, platform and numerical-library '
          'configuration are in the aggregate report.', '',
          '- [Frozen protocol](PROTOCOL.md) and [machine-readable specification](protocol.json)',
          '- [Aggregate results and provenance](results/results.json)',
          '- [Per-seed predictions, target ranks, timings and byte accounting](results/)', '',
          '```bash', 'python experiments/sign_ablation_v1/evaluate.py \\',
          f"  --registration-commit {result['registration_commit']} \\",
          '  --output outputs/sign_ablation_v1_replication', '```', '',
          'The output directory must be new. Sources are checked against the registration before '
          'execution. Numerical environments can affect floating-point details; timings and '
          'object sizes can vary. Run `python experiments/sign_ablation_v1/render_report.py` '
          'to regenerate this document from the saved observations without evaluating again.', '']
(HERE/'REPORT.md').write_text('\n'.join(lines))
print('Rendered REPORT.md from the saved observations')
