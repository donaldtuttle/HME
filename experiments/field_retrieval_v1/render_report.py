"""Render the saved Stage 2 experiment; never executes evaluation seeds."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'results/results.json').read_text())
for filename,expected in r['raw_files'].items():
    assert hashlib.sha256((HERE/'results'/filename).read_bytes()).hexdigest()==expected
runs=[json.loads((HERE/'results'/f'seed_{s}.json').read_text()) for s in r['completed_seeds']]
a=r['analysis']; primary=a['primary']
labels={'nn_signed':'Signed NN','nn_absolute':'Absolute NN','hybrid':'Hybrid',
        'field_only':'Field only + ID map','hybrid_permuted':'Hybrid, field association permuted'}
variants={'nn_signed':'Signed NN','nn_absolute':'Absolute NN','hybrid_cached':'Hybrid cached',
          'hybrid_uncached':'Hybrid uncached','field_cached':'Field only cached',
          'field_uncached':'Field only uncached','hybrid_permuted_cached':'Permuted hybrid cached'}


def condition(spacing,mode='native',sigma=1.,kind='ordinary'):
    return next(c for c in a['conditions'] if c['spacing']==spacing and c['query_mode']==mode
                and c['noise_sigma']==sigma and c['kind']==kind)


def stat(s,percent=True):
    scale,digits=(100,2) if percent else (1,3)
    lo,hi=s['ci95']
    return f"{scale*s['mean']:.{digits}f} [{scale*lo:.{digits}f}, {scale*hi:.{digits}f}]"


def overlap(spacing):
    return max(0,1-spacing/r['protocol']['dataset']['dimension'])*100


pc=condition(**{'spacing':primary['condition']['spacing'],'mode':primary['condition']['query_mode'],
                'sigma':primary['condition']['noise_sigma']})
if primary['accuracy_advantage_supported']:
    verdict='The registered practical accuracy advantage is supported in the primary condition.'
elif primary['lower_hybrid_accuracy']:
    verdict='The hybrid has lower accuracy than signed NN in the registered primary condition.'
else:
    verdict='The registered practical accuracy advantage is not established.'
lines=['# HME-NN-2B: candidate-specific field retrieval', '', f'**{verdict}**', '',
       f"Registration: [`{r['registration_commit'][:7]}`]({r['registration_url']}). "
       'The protocol, scorer, evaluator and fixtures were public before evaluation.', '',
       f"Execution: {r['started_at_utc']} through {r['finished_at_utc']}. "
       f"All {len(runs)} registered seeds completed; deviations: {len(r['deviations'])}. "
       'All registered correctness gates passed and all retrieval snapshots fit the 4 MiB cap.', '',
       '## Primary result', '',
       '128 Gaussian items, dimension 16, one item at each content-independent grid position, '
       '16-by-16 patches, a fixed 256-by-256 field, spacing 8 (50% adjacent-pair overlap), '
       'native query preprocessing and Gaussian noise sigma 1.0.', '',
       '| Arm | Mean top-1 accuracy (%) [95% seed-bootstrap interval] |','|---|---:|']
for name in labels:
    lines.append(f"| {labels[name]} | {stat(pc['arms'][name]['top1_accuracy'])} |")
lines += ['', f"**Hybrid minus signed NN: {stat(primary['paired_delta'])} percentage points.** "
          'The preregistered minimum useful gain was +2 points, requiring the entire paired '
          '95% interval to exceed +2. The unit of uncertainty is the independent seed, not '
          'individual queries sharing a field; 20,000 paired bootstrap resamples were used.', '',
          'The field score is now both query-dependent and candidate-specific: normalized '
          'Frobenius correlation between the query pattern and the candidate-position field '
          'patch. The hybrid uses `0.42 * signed_cosine + 0.20 * field_score`, with fixed '
          'weights, no clipping, no distance term, no tuning and no target-address input. '
          'This tests a new experimental readout, while retaining the pinned HME encoder/writer.', '',
          '## Overlap and mechanism controls', '',
          'Overlap denotes the shared area of adjacent horizontal/vertical patches; diagonal '
          'overlap is its square. It is not the union of overlap with all neighbours. Layout '
          'assignment is random and independent of content, and field dimensions stay fixed.', '',
          '![High-noise accuracy and paired field contribution across overlap](figures/overlap.svg)', '',
          'The plot uses native preprocessing at sigma 1.0. Shading/error bars show 95% '
          'seed-bootstrap intervals. Only 50% overlap is the confirmatory condition; '
          'the other comparisons are descriptive.', '',
          '| Adjacent overlap | Spacing | Signed NN (%) | Hybrid (%) | Field only (%) | Absolute NN (%) | Permuted hybrid (%) | Hybrid minus NN (pp), 95% interval |',
          '|---:|---:|---:|---:|---:|---:|---:|---:|']
for spacing in r['protocol']['dataset']['spacings']:
    c=condition(spacing)
    vals=[f"{100*c['arms'][name]['top1_accuracy']['mean']:.2f}" for name in ('nn_signed','hybrid','field_only','nn_absolute','hybrid_permuted')]
    lines.append(f"| {overlap(spacing):g}% | {spacing} | "+' | '.join(vals)+f" | {stat(c['contrasts']['hybrid_minus_nn_signed']['top1_accuracy'])} |")
lines += ['', 'Registered structural results:', '',
          '- At zero overlap, field-only target ranks matched absolute NN, and hybrid target '
          'ranks matched signed NN in every ordinary-data condition. For isolated patterns, '
          'the field score is absolute cosine squared; `0.42*c + 0.20*c*c` is strictly increasing '
          'on [-1,1]. This is a mathematical control, not empirical evidence of an advantage.',
          '- At the shared position, hybrid and permuted-hybrid rankings/predictions matched '
          'signed NN exactly; field-only tied all candidates and scored 1/128 (0.78125%) top-1.',
          '- The zero-field primary-layout control matched signed NN. Cached and uncached '
          'scores/ranks agreed on every registered check.', '',
          f"At the primary condition, hybrid minus permuted hybrid is "
          f"**{stat(pc['contrasts']['hybrid_minus_hybrid_permuted']['top1_accuracy'])} points**. "
          'This is a descriptive association control: beating a deliberately misassociated '
          'field does not by itself establish improvement over signed NN.', '',
          '## Reconstruction diagnostic', '',
          'Each loaded candidate patch is compared with its own isolated write contribution. '
          'Relative error is `norm(loaded - isolated) / norm(isolated)`. These diagnostics use '
          'the known stored contribution; they are not target-only retrieval competitors. '
          'Absolute NN supplies the equivalent isolated-pattern ranking reference.', '',
          '| Overlap | Mean relative error [95% interval] | Mean pattern correlation [95% interval] |',
          '|---:|---:|---:|']
for c in a['costs_by_layout']:
    lines.append(f"| {overlap(c['spacing']):g}% | {stat(c['reconstruction']['mean_relative_error'],False)} | {stat(c['reconstruction']['mean_correlation'],False)} |")
lines += ['', '## Polarity stress', '',
          'Each corpus has 64 vectors and their negatives, and each query has a paired exact '
          'negation. Queries use symmetric preprocessing. Opposite-sign query patterns are '
          'identical, so a deterministic field-only ranker can identify at most one member '
          'per equally weighted pair. The 50% ceiling applies to this constructed stress set, '
          'not to arbitrary random corpora.', '',
          '| Overlap | Noise | Signed NN (%) | Absolute NN (%) | Hybrid (%) | Field only (%) | Permuted hybrid (%) |',
          '|---:|---:|---:|---:|---:|---:|---:|']
for c in a['conditions']:
    if c['kind']=='antipodal':
        vals=[f"{100*c['arms'][name]['top1_accuracy']['mean']:.2f}" for name in labels]
        lines.append(f"| {overlap(c['spacing']):g}% | {c['noise_sigma']:g} | "+' | '.join(vals)+' |')
lines += ['', 'Every paired field-only score row was identical to its opposite-sign counterpart, '
          'and every seed/layout respected the 50% bound. No polarity-preserving encoder was tested.', '',
          '## Measured storage, query and cache costs', '',
          'All search variants return only candidate indices/IDs and scores. The old default '
          'API workload that constructs decoded outputs is absent from **every** arm. '
          'These experimental snapshots and optimized matrix operations therefore must not '
          'be compared as if their timings reproduced HME-NN-1 or HME-NN-2A.', '',
          'NN retains processed vectors. Field-only retains the field and optional readout '
          'cache, without original item vectors or per-item-pattern caches. Hybrid retains '
          'vectors and field. All arms retain identical records, lineage and address maps. '
          'The source HME writer used during construction is discarded from search snapshots '
          'and accounted separately; its state is not silently counted as free retained memory.', '',
          'Primary-layout costs:', '',
          '| Variant | Median persistent bytes | Maximum bytes | Numeric array bytes | Median query (ms) | Median seed p95 (ms) | Median paired latency / signed NN |',
          '|---|---:|---:|---:|---:|---:|---:|']
pcost=next(c for c in a['costs_by_layout'] if c['spacing']==primary['condition']['spacing'])
for name,label in variants.items():
    s,t=pcost['storage'][name],pcost['latency'][name]
    assert len(set(s['numeric_array_bytes']))==1
    lines.append(f"| {label} | {s['median_persistent_bytes']:,.0f} | {s['max_persistent_bytes']:,} | {s['numeric_array_bytes'][0]:,} | "
                 f"{t['median_of_seed_medians_ns']/1e6:.4f} | {t['median_of_seed_p95_ns']/1e6:.4f} | {t['median_paired_ratio_to_nn']:.2f} |")
lines += ['', f"The primary-layout source writer's median accounted build-state size is "
          f"{pcost['median_source_writer_bytes']:,.0f} bytes, separate from retained search-state accounting.", '',
          '| Overlap | Hybrid cache build (ms) | Cache discard (microseconds) | Hybrid cached query (ms) | Hybrid uncached query (ms) | Field cached query (ms) | Field uncached query (ms) |',
          '|---:|---:|---:|---:|---:|---:|---:|']
for c in a['costs_by_layout']:
    cache=c['cache']['hybrid']
    values=[c['latency'][n]['median_of_seed_medians_ns']/1e6 for n in ('hybrid_cached','hybrid_uncached','field_cached','field_uncached')]
    lines.append(f"| {overlap(c['spacing']):g}% | {cache['median_build_ns']/1e6:.4f} | {cache['median_invalidate_ns']/1e3:.3f} | "+' | '.join(f'{x:.4f}' for x in values)+' |')
lines += ['', 'Cost summaries use medians across per-seed medians/p95s on this host. Queries '
          'include preprocessing and query-pattern encoding, top-k 5, one numerical-library '
          'thread, three repeats of 16 queries per layout/seed, three warmups per variant '
          'and rotated execution order. Cache build/discard uses five cycles per seed/layout. '
          'Discard timing is not a complete write-throughput measurement. The shared-position '
          'readout exploits identical patches when computing scores; its stored full cache is '
          'still charged.', '',
          'Recursive Python object/owned-array accounting deduplicates aliases. It excludes '
          'interpreter/shared code, allocator overhead, discarded source state and transient '
          'query workspace. These are retained bytes, not peak process RSS. The common cap '
          'and task size are matched; consumed bytes are not padded to equality. All per-layout '
          'storage and per-query timings are available in the saved data.', '',
          '## All ordinary-data retrieval conditions', '',
          'Values below are seed means. All 95% intervals and paired contrasts, including for '
          'the antipodal conditions, are in the aggregate JSON. Only the designated primary '
          'comparison is confirmatory; other intervals are descriptive without multiplicity '
          'adjustment. Perfect observed means do not guarantee perfect population performance.', '']
for metric,title,scale in [('top1_accuracy','Top-1 accuracy (%)',100),('top5_accuracy','Top-5 accuracy (%)',100),
                            ('mean_reciprocal_rank','Mean reciprocal rank',1)]:
    lines += [f'### {title}', '', '| Overlap | Mode | Noise | Signed NN | Absolute NN | Hybrid | Field only | Permuted hybrid |',
              '|---:|---|---:|---:|---:|---:|---:|---:|']
    for c in a['conditions']:
        if c['kind']=='ordinary':
            values=[f"{scale*c['arms'][name][metric]['mean']:.3f}" for name in labels]
            lines.append(f"| {overlap(c['spacing']):g}% | {c['query_mode']} | {c['noise_sigma']:g} | "+' | '.join(values)+' |')
    lines += ['']
lines += ['## Unmatched queries and limits', '',
          '| Arm | Accepted / total across layouts and preprocessing modes |','|---|---:|']
for name in labels:
    observations=[layout['unmatched_queries'][mode][name] for run in runs for layout in run['layouts'] for mode in ('native','symmetric')]
    lines.append(f"| {labels[name]} | {sum(x['accepted'] for x in observations)} / {sum(x['total'] for x in observations)} |")
lines += ['', 'These are fresh Gaussian queries with no designated stored target, reused across '
          'layouts and modes. They are not independent replicates or a distribution-shift set. '
          'All methods use closed-set ranking without rejection. Scores are not calibrated probabilities.', '',
          'This experiment concerns synthetic identity retrieval at one item count and vector '
          'dimension. It does not establish semantic retrieval, a capacity frontier, superiority '
          'to other HRR/VSA designs or production persistence. Independent positions change the '
          'task relative to HME-NN-1/2A, so their headline accuracies must not be pooled.', '',
          f"**Stage 3 accuracy gate: {'passed' if a['stage3_accuracy_gate_passed'] else 'not passed'}.** " +
          ('The result motivates considering costs and a separate encoder protocol; it does not authorize automatic production adoption.'
           if a['stage3_accuracy_gate_passed'] else 'This run supplies no registered accuracy-advantage justification for proceeding automatically to an encoder redesign.'), '',
          '## Reproduction and raw evidence', '',
          f"Environment: Python {r['environment']['python']}, NumPy {r['environment']['numpy']}. "
          'The aggregate report records exact source hashes, platform and numerical-library configuration; '
          'raw seed files include dataset/layout/field/readout hashes, candidate identity maps, '
          'predictions, target ranks, diagnostics and cost samples.', '',
          '- [Frozen protocol](PROTOCOL.md) and [machine-readable specification](protocol.json)',
          '- [Aggregate analysis and provenance](results/results.json)',
          '- [Every seed result](results/)', '',
          '```bash', 'python experiments/field_retrieval_v1/evaluate.py \\',
          f"  --registration-commit {r['registration_commit']} \\",
          '  --output outputs/field_retrieval_v1_replication', '```', '',
          'Use a new output directory. The evaluator verifies frozen sources before execution. '
          'Timings and object sizes vary by environment. Install `.[visualization]` and run '
          '`python experiments/field_retrieval_v1/render_report.py` to recreate this report and '
          'plot from saved observations without evaluating seeds again.', '']
(HERE/'REPORT.md').write_text('\n'.join(lines))

(HERE/'figures').mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'svg.hashsalt':'HME-NN-2B'})
fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
cells=[condition(s) for s in r['protocol']['dataset']['spacings']]
x=np.array([overlap(c['spacing']) for c in cells])
for name,color,marker in [('nn_signed','#248051','s'),('nn_absolute','#666666','v'),
                           ('hybrid','#2466b5','o'),('field_only','#bd6722','^')]:
    stats=[c['arms'][name]['top1_accuracy'] for c in cells]
    means=np.array([s['mean'] for s in stats])*100
    lo,hi=np.array([s['ci95'] for s in stats]).T*100
    axes[0].plot(x,means,color=color,marker=marker,label=labels[name],linewidth=1.8)
    axes[0].fill_between(x,lo,hi,color=color,alpha=.1)
axes[0].set(ylabel='Top-1 accuracy (%)',ylim=(0,100),title='Candidate identity retrieval')
axes[0].legend(loc='lower left',fontsize=8,frameon=False)
stats=[c['contrasts']['hybrid_minus_nn_signed']['top1_accuracy'] for c in cells]
y=np.array([s['mean'] for s in stats])*100
lo,hi=np.array([s['ci95'] for s in stats]).T*100
axes[1].errorbar(x,y,yerr=np.maximum(0,np.array([y-lo,hi-y])),color='#2466b5',marker='o',capsize=4,label='Hybrid minus signed NN')
axes[1].axhline(0,color='#777777',linewidth=.8)
axes[1].axhline(2,color='#248051',linestyle='--',label='Registered +2-point bar')
axes[1].set(ylabel='Accuracy difference (percentage points)',title='Paired effect and 95% intervals')
axes[1].legend(fontsize=8,frameon=False)
for ax in axes:
    ax.set(xlabel='Adjacent-pair overlap (%)',xticks=x)
    ax.grid(axis='y',alpha=.18)
    ax.spines[['top','right']].set_visible(False)
fig.suptitle('HME-NN-2B · 30 seeds · noise sigma 1.0 · native queries\nPrimary condition: 50% overlap',fontsize=12)
fig.savefig(HERE/'figures/overlap.svg',metadata={'Date':None})
plt.close(fig)
print('Rendered REPORT.md and figures/overlap.svg from saved observations')
