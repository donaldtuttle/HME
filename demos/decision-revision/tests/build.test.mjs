import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

test('static build uses local relative assets and packages the current source', () => {
  const root = resolve('dist/client');
  const html = readFileSync(resolve(root, 'index.html'), 'utf8');
  assert.match(html, /Decision Revision Bench/);
  assert.doesNotMatch(html, /https?:\/\/|\/__grok\//);
  for (const match of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    assert.ok(match[1].startsWith('./'), match[1]);
    assert.ok(statSync(resolve(root, match[1])).isFile());
  }
  const css = readdirSync(resolve(root, 'assets')).filter(name => name.endsWith('.css')).map(name => readFileSync(resolve(root, 'assets', name), 'utf8')).join('\n');
  assert.match(css, /@font-face/);
  for (const match of css.matchAll(/url\((?:["']?)([^)"']+)(?:["']?)\)/g)) {
    if (match[1].startsWith('data:')) continue;
    assert.doesNotMatch(match[1], /^(?:https?:|\/)/);
    assert.ok(statSync(resolve(root, 'assets', match[1])).isFile(), match[1]);
  }
});
