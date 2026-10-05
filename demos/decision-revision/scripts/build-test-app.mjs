import { build } from 'esbuild';
await build({
  entryPoints: ['src/Workbench.tsx'],
  outfile: 'outputs/test-app.mjs',
  bundle: true,
  platform: 'node',
  format: 'esm',
  jsx: 'automatic',
  external: ['react', 'react-dom', 'react/jsx-runtime', 'lucide-react'],
});
