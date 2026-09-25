"""Render the registered results without rerunning or changing the experiment."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
result = json.loads((HERE/'results/results.json').read_text())
for filename, expected in result['raw_files'].items():
    assert hashlib.sha256((HERE/'results'/filename).read_bytes()).hexdigest() == expected
runs = [json.loads((HERE/'results'/f'seed_{seed}.json').read_text())
        for seed in result['completed_seeds']]
a = result['analysis']
p = a['primary']
labels = {'hme': 'HME', 'nn_cosine': 'Signed cosine NN',
          'nn_absolute': 'Absolute cosine NN', 'hme_field_erased': 'HME, field erased'}


def estimate(stat, percent=False):
    scale = 100 if percent else 1
    suffix = '%' if percent else ''
    digits = 2 if percent else 3
    lo, hi = stat['ci95']
    return f"{scale*stat['mean']:.{digits}f}{suffix} [{scale*lo:.{digits}f}, {scale*hi:.{digits}f}]"


def get_cell(mode, sigma):
    return next(c for c in a['conditions'] if c['query_mode'] == mode and c['noise_sigma'] == sigma)


primary = get_cell('native', 1.)
lines = [
    '# HME-NN-1: preregistered nearest-neighbor results', '',
    f"Registration: [`{result['registration_commit'][:7]}`]({result['registration_url']}). "
    'The protocol, evaluator and correctness fixtures were pushed before the registered seeds ran.', '',
    f"Execution: {result['started_at_utc']} through {result['finished_at_utc']}. "
    f"All {len(runs)} registered seeds completed. Protocol deviations: {len(result['deviations'])}. "
    'The engine source is unchanged.', '',
    '## Primary result', '',
    f"Registered decision: **`{p['decision']}`**.", '',
    'The current HME ranker lost to exact signed-cosine nearest neighbors in the '
    'registered primary comparison, with lower accuracy on all ten seeds. For this '
    'tested retrieval task, exact NN with the same retained provenance is the better '
    'default. The result does not support a retrieval advantage for HME.', '',
    'The primary condition is native query preprocessing, Gaussian noise sigma 1.0, '
    '128 candidates and dimension 16. The primary metric is top-1 identity accuracy.', '',
    '| Method or paired contrast | Mean and paired-seed bootstrap 95% interval |',
    '|---|---:|',
    f"| HME | {estimate(p['hme'], True)} |",
    f"| Signed cosine NN | {estimate(p['nn_cosine'], True)} |",
    f"| HME minus signed cosine NN (percentage points) | {estimate(p['paired_delta'], True).replace('%', '')} |", '',
    'The preregistered advantage rule required the lower interval endpoint to exceed '
    '+2 percentage points, with both methods inside the common 4 MiB storage cap. '
    'All arms fit the cap. The uncertainty unit is the independent seed, not an individual '
    'query sharing a field: 20,000 paired bootstrap resamples of ten seed-level means.', '',
    '## All registered retrieval conditions', '',
    'The primary cell above is confirmatory. Every other cell and contrast is descriptive; '
    'intervals below are not adjusted for multiple comparisons. NN methods retain copies of '
    'the exact processed vectors, artifact records and lineage available to HME. '
    'All items share one position; no target identity is supplied to retrieval.', '',
    '![Top-1 accuracy across noise and preprocessing](figures/top1.svg)', '',
]
for metric, title, percent in [('top1_accuracy', 'Top-1 accuracy', True),
                                ('top5_accuracy', 'Top-5 accuracy', True),
                                ('mean_reciprocal_rank', 'Mean reciprocal rank', False)]:
    lines += [f'### {title}', '', '| Query mode | Noise sigma | HME | Signed cosine NN | Absolute NN / field-erased HME |',
              '|---|---:|---:|---:|---:|']
    for cell in a['conditions']:
        values = [estimate(cell['arms'][name][metric], percent)
                  for name in ('hme', 'nn_cosine', 'nn_absolute')]
        lines.append(f"| {cell['query_mode']} | {cell['noise_sigma']:g} | " + ' | '.join(values) + ' |')
    lines += ['']
lines += ['The absolute-NN and field-erased HME target ranks matched for every query in every '
          'registered cell. A zero-width interval at perfect observed accuracy describes these '
          'seeds; it is not a population guarantee.', '',
          '### Primary result by seed', '',
          '| Seed | HME correct / 128 | Signed NN correct / 128 | Absolute NN correct / 128 |',
          '|---:|---:|---:|---:|']
for run in runs:
    cell = next(c for c in run['cells'] if c['query_mode'] == 'native' and c['noise_sigma'] == 1.)
    counts = [sum(rank == 1 for rank in cell['arms'][name]['target_ranks'])
              for name in ('hme', 'nn_cosine', 'nn_absolute')]
    lines.append(f"| {run['seed']} | " + ' | '.join(map(str, counts)) + ' |')
lines += ['', '## Field contribution and acceptance', '',
          'At the primary condition, HME minus absolute NN (equivalently field-erased HME) is '
          f"**{estimate(primary['hme_minus']['nn_absolute']['top1_accuracy'], True).replace('%', '')} percentage points**. "
          'This isolates the field contribution while retaining the current absolute-similarity rule. '
          'It is a descriptive mechanism check, not a replacement primary.', '',
          'At this shared position and with salience off, erasing the field leaves '
          '`score = 0.38 + 0.42 * absolute_cosine`, which preserves the absolute-NN ordering. '
          'The full ranker adds `0.20 * pattern_score`; this term depends on the stored '
          'candidate and field, but not on the current query.', '',
          '| Method | Unmatched queries accepted / total (both query modes) |', '|---|---:|']
for name in labels:
    obs = [run['unmatched_queries'][mode][name] for run in runs for mode in ('native', 'symmetric')]
    lines.append(f"| {labels[name]} | {sum(o['accepted'] for o in obs)} / {sum(o['total'] for o in obs)} |")
lines += ['', 'These queries are fresh Gaussian vectors without a designated stored target, '
          'not a distribution-shift set. Default closed-set acceptance is not calibrated correctness '
          'or evidence of useful rejection. No Brier/ECE value is computed from raw ranking scores.', '',
          f"Removing the records and cached vectors/patterns while retaining the field returned "
          f"zero identified hits in {sum(r['field_only_check']['hit_count'] == 0 for r in runs)}/{len(runs)} structural checks. "
          'The decoded surfaces remained nonzero. The current API needs retained records to attach identities.', '',
          '## Persistent storage and online API latency', '',
          '| Method | Median persistent bytes | Maximum persistent bytes | Numeric array bytes | Median query latency (ms) | Median seed p95 (ms) |',
          '|---|---:|---:|---:|---:|---:|']
for name in labels:
    s, t = a['storage'][name], a['latency'][name]
    assert len(set(s['numeric_array_bytes'])) == 1
    lines.append(f"| {labels[name]} | {s['median_persistent_bytes']:,.0f} | {s['max_persistent_bytes']:,} | "
                 f"{s['numeric_array_bytes'][0]:,} | {t['median_of_seed_medians_ns']/1e6:.4f} | {t['median_of_seed_p95_ns']/1e6:.4f} |")
ratio = a['storage']['hme']['median_persistent_bytes']/a['storage']['nn_cosine']['median_persistent_bytes']
lines += ['', f"HME retains **{ratio:.2f} times** the median accounted storage of signed NN. "
          f"The median paired HME/NN query-latency ratio is **{a['hme_over_nn_cosine_latency_ratio']['median']:.1f} times**.", '',
          'Storage is recursive CPython object accounting, including arrays, field, cached patterns, '
          'records, provenance and containers, with aliases counted once. It excludes interpreter, '
          'shared libraries, allocator overhead and temporary query buffers. This is a common maximum '
          'budget at equal task size, not an equal-consumed-byte capacity frontier.', '',
          'Latency uses 32 primary-condition queries per seed, four warmups per arm, three repetitions, '
          'rotated method order, top-k 5, and one numerical-library thread. Values are medians of '
          'per-seed medians/p95s on this shared host. HME also produces reconstructed outputs; '
          'NN only returns IDs and scores. These are current implementation/API costs, not intrinsic '
          'algorithmic lower bounds or equivalent-output microbenchmarks.', '',
          '## Scope and reproducibility', '',
          'This experiment covers synthetic Gaussian identity retrieval at one load, dimension and '
          'shared position. It does not establish semantic text retrieval, performance with useful '
          'spatial cues, HRR/VSA comparisons, field-controller/salience efficacy, calibrated rejection, '
          'production persistence or a storage-capacity frontier. Those remain later stages of '
          '[the evaluation plan](../../docs/EVALUATION_PLAN.md).', '',
          f"Environment: Python {result['environment']['python']}, NumPy {result['environment']['numpy']}; "
          'the raw report records the platform, numerical-library configuration, thread settings, '
          'source hashes and dataset hashes.', '',
          '- [Frozen protocol](PROTOCOL.md) and [machine-readable specification](protocol.json)',
          '- [Aggregate results and provenance](results/results.json)',
          '- [Per-seed raw predictions, ranks, timings and costs](results/)', '',
          'From the repository checkout, with NumPy installed:', '', '```bash',
          'python experiments/nn_baseline_v1/evaluate.py \\',
          f"  --registration-commit {result['registration_commit']} \\",
          '  --output outputs/nn_baseline_v1_replication',
          '```', '',
          'The output directory must not already exist. The evaluator verifies the frozen sources '
          'against the registration commit. Accuracy and rankings are deterministic for these inputs '
          'and compatible numerical environments; timings and Python object sizes can differ. '
          'Install `.[visualization]` and run `python experiments/nn_baseline_v1/render_report.py` '
          'to redraw this report from the committed results without rerunning evaluation.', '']
(HERE/'REPORT.md').write_text('\n'.join(lines))

plt.rcParams.update({'font.size': 10, 'svg.hashsalt': 'HME-NN-1'})
fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), sharey=True, layout='constrained')
for ax, mode in zip(axes, ('native', 'symmetric')):
    cells = [c for c in a['conditions'] if c['query_mode'] == mode]
    x = [c['noise_sigma'] for c in cells]
    for name, color, marker in [('hme', '#b33b32', 'o'), ('nn_cosine', '#146ca4', 's'),
                                ('nn_absolute', '#3d7e53', '^')]:
        stats = [c['arms'][name]['top1_accuracy'] for c in cells]
        mean = np.array([s['mean'] for s in stats])*100
        low, high = np.array([s['ci95'] for s in stats]).T*100
        label = labels[name] if name != 'nn_absolute' else 'Absolute NN = field-erased HME'
        ax.plot(x, mean, marker=marker, color=color, label=label, linewidth=1.8, markersize=5)
        ax.fill_between(x, low, high, color=color, alpha=.12)
    ax.set(title=f'{mode.capitalize()} query preprocessing', xlabel='Gaussian query noise (sigma)',
           xticks=x, ylim=(0, 104))
    ax.grid(axis='y', alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_ylabel('Top-1 identity accuracy (%)')
axes[0].legend(loc='lower left', fontsize=8, frameon=False)
fig.suptitle('HME-NN-1: ten seeds, 128 items, dimension 16', fontsize=13)
fig.savefig(HERE/'figures/top1.svg', metadata={'Date': None})
plt.close(fig)
print('Rendered REPORT.md and figures/top1.svg from committed observations')
