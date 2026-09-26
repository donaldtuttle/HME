import test, {afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/'});
for(const key of ['window','document','HTMLElement','Element','Node','Event','MouseEvent','KeyboardEvent','MutationObserver'])globalThis[key]=dom.window[key];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
// jsdom is a DOM check only: no layout, raster, or browser rendering is claimed.
globalThis.ResizeObserver=class{observe(){} disconnect(){}};
const React=await import('react');
const {render,screen,fireEvent,cleanup,within}=await import('@testing-library/react');
const {default:App}=await import('../.test-build/App.mjs');
afterEach(cleanup);
const mount=()=>render(React.createElement(App));
const click=name=>fireEvent.click(screen.getByRole('button',{name,exact:true}));
const change=(name,value)=>fireEvent.change(screen.getByLabelText(name,{exact:true}),{target:{value}});
const section=name=>screen.getByRole('heading',{name,exact:true}).closest('section');
test('Hann-off then reset restores the initial score and checked setting',()=>{
 mount();assert.match(document.body.textContent,/relevance 0\.891/);
 fireEvent.click(screen.getByLabelText('Hann window on later writes'));click('Reset demo plate');
 assert.equal(screen.getByLabelText('Hann window on later writes').checked,true);
 assert.match(document.body.textContent,/energy 0\.196/);assert.match(document.body.textContent,/relevance 0\.891/);
});
test('probe uses threshold and labels old results after a setting change',()=>{
 mount();change('Threshold','1');click('Run top-1 probe');
 assert.equal(within(screen.getByRole('table')).getAllByText('0/8').length,4);
 assert.match(document.body.textContent,/Counted at threshold 1\.00/);
 change('Threshold','0');assert.match(document.body.textContent,/Retrieval threshold is now 0\.00; run again to use it/);
 click('Run top-1 probe');assert.equal(within(screen.getByRole('table')).getAllByText('8/8').length,3);
});
test('ledger drop renders All zeros without visible nonzero bar heights',()=>{
 mount();click('Drop ledger, keep field');assert.ok(screen.getByText('All zeros'));
 assert.ok(screen.getByText('No retained records.'));assert.ok(screen.getByText('NO_MATCH',{exact:true}));
 const title=screen.getByText('Decoded vector',{exact:true});
 assert.equal(title.parentElement.querySelectorAll('[style*="height"]').length,0);
 assert.equal(screen.getByRole('button',{name:'Run top-1 probe'}).disabled,true);
});
test('vector write, invalid input, and symbol write update their own controls',()=>{
 mount();change('Numeric item','nonsense');click('Encode into plate');assert.ok(screen.getByText('Vector needs finite numbers, separated by commas.'));
 change('Numeric item','0.3, 0.1, 0.6, 0.8');click('Encode into plate');assert.match(document.body.textContent,/5 records/);assert.ok(screen.getByRole('button',{name:/^reading-004/}));
 fireEvent.click(within(screen.getByRole('group',{name:'Write kind'})).getByRole('button',{name:'Symbol'}));
 change('Exact symbol','dock');click('Encode into plate');assert.match(document.body.textContent,/6 records/);assert.ok(screen.getByRole('button',{name:/^symbol:dock/}));
});
test('query modes, field view, keyboard placement and details remain interactive',()=>{
 mount();click('Phase');assert.equal(screen.getByRole('button',{name:'Phase'}).getAttribute('aria-pressed'),'true');
 click('Place query');fireEvent.keyDown(screen.getByRole('application'),{key:'ArrowRight'});assert.match(document.body.textContent,/Query \(20, 23\)/);
 const modes=screen.getByRole('group',{name:'Query mode'});
 fireEvent.click(within(modes).getByRole('button',{name:'Vector'}));change('Query vector','NaN');assert.ok(screen.getByText('Query vector needs finite numbers.'));
 fireEvent.click(within(modes).getByRole('button',{name:'Symbol'}));change('Query symbol','beacon');assert.match(document.body.textContent,/Symbol queries use the raw seeded vector/);
 fireEvent.click(within(modes).getByRole('button',{name:'Spatial'}));assert.match(document.body.textContent,/No query vector/);
});
test('field erase removes pattern scores and reset clears probe results',()=>{
 mount();click('Run top-1 probe');click('Erase field, keep ledger');assert.match(document.body.textContent,/energy 0\.000/);assert.match(document.body.textContent,/relevance 0\.731/);assert.equal(screen.queryByRole('table'),null);
 click('Reset demo plate');assert.match(document.body.textContent,/relevance 0\.891/);
});
