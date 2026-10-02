import { CORPUS } from './corpus.ts';
import { PREFLIGHT, ARM_SUMMARY, BASELINE_SUMMARY } from './report.ts';
console.log(JSON.stringify({
  status: 'DESIGN',
  field_status: 'MECHANISM_NOT_TESTED',
  histories: CORPUS.length,
  preflight: PREFLIGHT,
  packet_diagnostics: ARM_SUMMARY,
  baselines: BASELINE_SUMMARY,
}, null, 2));
if (PREFLIGHT.some(check => !check.pass)) process.exitCode = 1;
