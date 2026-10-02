import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/HME/decision-revision/' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement } = await import('react');
const { render, screen, fireEvent, cleanup } = await import('@testing-library/react');
const { Workbench } = await import('../outputs/test-app.mjs');
afterEach(cleanup);

const answer = JSON.stringify({ decisions: [
  { decision_id: 'D_ALDER', action: 'REVISE', selected_option_id: 'RIG_B', decisive_premise_ids: ['P_SHADOW', 'P_DEADLINE'], unresolved_premise_ids: [], evidence_ids: ['E01', 'E02', 'E03', 'E05'] },
  { decision_id: 'D_BIRCH', action: 'RETAIN', selected_option_id: 'RIG_A', decisive_premise_ids: ['P_SHADOW'], unresolved_premise_ids: [], evidence_ids: ['E01', 'E04'] },
] });
function openReader() {
  render(createElement(Workbench));
  fireEvent.click(screen.getByRole('button', { name: 'Open the worked example' }));
}
function primary() { return screen.getByText('Primary outcome').nextElementSibling.textContent; }

test('worked example scores, gates reveal, and clears stale results on edit', () => {
  openReader();
  assert.equal(screen.queryByRole('button', { name: 'Reveal evaluator key' }), null);
  fireEvent.click(screen.getByRole('button', { name: 'Score this response' }));
  assert.equal(primary(), '0');
  fireEvent.change(screen.getByRole('textbox', { name: 'Decision JSON' }), { target: { value: answer } });
  assert.equal(screen.queryByText('Primary outcome'), null);
  assert.equal(screen.queryByRole('button', { name: 'Reveal evaluator key' }), null);
  fireEvent.click(screen.getByRole('button', { name: 'Score this response' }));
  assert.equal(primary(), '1');
  fireEvent.click(screen.getByRole('button', { name: 'Reveal evaluator key' }));
  assert.ok(screen.getByText(/Evaluator key ·/));
  fireEvent.change(screen.getByRole('textbox', { name: 'Decision JSON' }), { target: { value: answer + '\n' } });
  assert.equal(screen.queryByText(/Evaluator key ·/), null);
  assert.equal(screen.queryByText('Primary outcome'), null);
});

test('packet and history drafts remain separate and missing evidence prevents grounded success', () => {
  openReader();
  const editor = () => screen.getByRole('textbox', { name: 'Decision JSON' });
  fireEvent.change(editor(), { target: { value: answer } });
  fireEvent.click(screen.getByRole('button', { name: 'Lexical NN (projected)', exact: true }));
  assert.notEqual(editor().value, answer);
  fireEvent.change(editor(), { target: { value: answer } });
  fireEvent.click(screen.getByRole('button', { name: 'Score this response' }));
  assert.equal(primary(), '0');
  fireEvent.click(screen.getByRole('button', { name: 'Decision ledger', exact: true }));
  assert.equal(editor().value, answer);
  assert.equal(screen.queryByText('Primary outcome'), null);
  fireEvent.change(screen.getByRole('combobox', { name: 'History' }), { target: { value: 'alder-cc-2' } });
  assert.notEqual(editor().value, answer);
  fireEvent.change(screen.getByRole('combobox', { name: 'History' }), { target: { value: 'alder-cc-1' } });
  assert.equal(editor().value, answer);
});

test('malformed input shows a format failure without exposing the key', () => {
  openReader();
  fireEvent.change(screen.getByRole('textbox', { name: 'Decision JSON' }), { target: { value: '{broken' } });
  fireEvent.click(screen.getByRole('button', { name: 'Score this response' }));
  assert.ok(screen.getByRole('heading', { name: 'Format failure' }));
  assert.equal(screen.queryByRole('button', { name: 'Reveal evaluator key' }), null);
});

test('source links support subpaths and Checks shows the corrected retain baseline', () => {
  render(createElement(Workbench));
  for (const link of screen.getAllByRole('link', { name: 'decision_revision_v1.zip' })) {
    assert.equal(link.getAttribute('href'), './decision_revision_v1.zip');
    assert.equal(new URL(link.href).pathname, '/HME/decision-revision/decision_revision_v1.zip');
  }
  fireEvent.click(screen.getByRole('button', { name: 'Checks', exact: true }));
  assert.match(screen.getByText('Always retain').closest('li').textContent.replace(/\s+/g, ' '), /action-only 16\s*\/\s*32/);
  assert.ok(screen.getByText(/All fixture checks passed\./));
  assert.ok(screen.getByText('MECHANISM_NOT_TESTED'));
});
