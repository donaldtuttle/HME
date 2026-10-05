import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
const root='dist/client';
test('built entry and asset references work below a repository subpath',()=>{
 const entry=fs.readFileSync(path.join(root,'index.html'),'utf8');assert.match(entry,/<title>HME Plate<\/title>/);
 for(const [,ref] of entry.matchAll(/(?:src|href)="([^"]+)"/g)){assert.ok(ref.startsWith('./'),ref);assert.ok(fs.existsSync(path.join(root,ref)),ref);}
 const assetFiles=fs.readdirSync(path.join(root,'assets'));
 const css=assetFiles.filter(f=>f.endsWith('.css')).map(f=>fs.readFileSync(path.join(root,'assets',f),'utf8')).join('\n');
 for(const [,url] of css.matchAll(/url\(([^)]+)\)/g)){const clean=url.replace(/["']/g,'');assert.ok(!/^https?:/.test(clean),clean);assert.ok(fs.existsSync(path.join(root,'assets',clean)),clean);}
 const scripts=assetFiles.filter(f=>f.endsWith('.js')).map(f=>fs.readFileSync(path.join(root,'assets',f),'utf8')).join('\n');assert.ok(!scripts.includes('grok-app-builder'));assert.ok(!scripts.includes('fonts.googleapis.com'));
});
