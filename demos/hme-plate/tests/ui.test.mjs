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

test('Explore opens with compact onboarding and reset preserves the seeded result',()=>{
 mount();
 assert.ok(screen.getByRole('heading',{name:'Explore HME',exact:true}));
 assert.equal(screen.getByText('Quick start',{exact:true}).closest('details').open,false);
 assert.match(document.body.textContent,/Match score 0\.891/);
 fireEvent.click(screen.getByLabelText('Soften edges on later stores',{exact:true}));
 click('Restore the demo');
 assert.equal(screen.getByLabelText('Soften edges on later stores',{exact:true}).checked,true);
 assert.match(document.body.textContent,/energy 0\.196/);
 assert.match(document.body.textContent,/Match score 0\.891/);
});

test('probe uses threshold and labels old results after a setting change',()=>{
 mount();change('Threshold','1');click('Run the test');
 assert.equal(within(screen.getByRole('table')).getAllByText('0/8').length,4);
 assert.match(document.body.textContent,/Counted at threshold 1\.00/);
 change('Threshold','0');assert.match(document.body.textContent,/Retrieval threshold is now 0\.00; run again to use it/);
 click('Run the test');assert.equal(within(screen.getByRole('table')).getAllByText('8/8').length,3);
});

test('record removal keeps the field and Details exposes zero decoded output',()=>{
 mount();click('Details');click('Remove records, keep field');
 assert.ok(screen.getByText('All zeros'));
 assert.ok(screen.getByText('No retained records.'));
 assert.ok(screen.getByText('NO_MATCH',{exact:true}));
 const title=screen.getByText('Decoded vector',{exact:true});
 assert.equal(title.parentElement.querySelectorAll('[style*="height"]').length,0);
 assert.equal(screen.getByRole('button',{name:'Run the test'}).disabled,true);
});

test('vector write, invalid input, and symbol write update the friendly controls',()=>{
 mount();change('Values','nonsense');click('Store memory');assert.ok(screen.getByText('Vector needs finite numbers, separated by commas.'));
 change('Values','0.3, 0.1, 0.6, 0.8');click('Store memory');assert.match(document.body.textContent,/5 records/);assert.ok(screen.getByRole('button',{name:/^reading-004/}));
 fireEvent.click(within(screen.getByRole('group',{name:'Write kind'})).getByRole('button',{name:'Symbol'}));
 change('Exact symbol','dock');click('Store memory');assert.match(document.body.textContent,/6 records/);assert.ok(screen.getByRole('button',{name:/^symbol:dock/}));
});

test('search modes, field view, keyboard placement and plain-language notes remain interactive',()=>{
 mount();click('Phase');assert.equal(screen.getByRole('button',{name:'Phase'}).getAttribute('aria-pressed'),'true');
 click('Place search');fireEvent.keyDown(screen.getByRole('application'),{key:'ArrowRight'});assert.match(document.body.textContent,/Search position \(20, 23\)/);
 const modes=screen.getByRole('group',{name:'Search mode'});
 assert.match(modes.className,/search-mode-grid/);
 fireEvent.click(within(modes).getByRole('button',{name:'Vector'}));change('Search values','NaN');assert.ok(screen.getByText('Query vector needs finite numbers.'));
 fireEvent.click(within(modes).getByRole('button',{name:'Symbol'}));change('Search symbol','beacon');assert.match(document.body.textContent,/Searching for that exact symbol/);
 fireEvent.click(within(modes).getByRole('button',{name:'Spatial'}));assert.match(document.body.textContent,/Searching by place only/);
});

test('field erase removes pattern contribution and restore clears probe results',()=>{
 mount();click('Run the test');click('Erase field, keep records');
 assert.match(document.body.textContent,/energy 0\.000/);
 assert.match(document.body.textContent,/Match score 0\.731/);
 assert.equal(screen.queryByRole('table'),null);
 click('Restore the demo');assert.match(document.body.textContent,/Match score 0\.891/);
});

test('Details restores technical vocabulary and deeper readouts',()=>{
 mount();click('Details');
 assert.ok(screen.getByRole('heading',{name:'Scoring',exact:true}));
 assert.match(document.body.textContent,/relevance 0\.891/);
 assert.match(document.body.textContent,/Hann window/);
 assert.match(document.body.textContent,/numeric vector/);
 assert.match(document.body.textContent,/ledger/);
 assert.ok(screen.getByText('Decoded vector',{exact:true}));
 assert.ok(screen.getByText('Search window',{exact:true}));
});
