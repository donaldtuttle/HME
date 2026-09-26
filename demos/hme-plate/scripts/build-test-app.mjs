import { build } from 'esbuild';
await build({entryPoints:['src/App.jsx'],bundle:true,platform:'node',format:'esm',jsx:'automatic',packages:'external',outfile:'.test-build/App.mjs'});
