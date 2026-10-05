import test from 'node:test';
import assert from 'node:assert/strict';
import {ViewerEngine, createDemoState, resolveQuery, runViewerChecks, runNoiseProbe, parseNumericInput, addNoise} from '../src/model.js';
for(const result of runViewerChecks()) test(`source check: ${result.name}`,()=>assert.equal(result.pass,true,result.detail));
test('noise probe has explicit threshold and deterministic results',()=>{
 const {engine,form}=createDemoState();
 const open=runNoiseProbe(engine,form.selectedId,[0,.25,.5,1],8,{threshold:0,radius:4});
 const shut=runNoiseProbe(engine,form.selectedId,[0,.25,.5,1],8,{threshold:1,radius:4});
 assert.deepEqual(open.cells.map(c=>c.hits),[8,8,8,4]);
 assert.deepEqual(shut.cells.map(c=>c.hits),[0,0,0,0]);
 assert.equal(shut.threshold,1);assert.equal(shut.radius,4);
 assert.deepEqual(open,runNoiseProbe(engine,form.selectedId,[0,.25,.5,1],8,{threshold:0,radius:4}));
});
test('field and ledger ablations preserve distinct outputs',()=>{
 const {engine,form}=createDemoState(), before=resolveQuery(engine,form).retrieval;
 engine.eraseField();const erased=resolveQuery(engine,form).retrieval;
 assert.equal(erased.hits[0].artifactId,before.hits[0].artifactId);
 assert.equal(erased.hits[0].patternScore,0);assert.ok(erased.decodedRe.some(v=>v!==0));
 const other=createDemoState().engine, energy=other.energy();other.dropLedger();
 const dropped=other.retrieve([20,22],{query:null});
 assert.equal(other.energy(),energy);assert.equal(dropped.outcome,'NO_MATCH');assert.ok(dropped.decodedRe.every(v=>v===0));assert.ok(dropped.surfaceMag.some(v=>v>0));
});
test('eviction discards the cached record but preserves its field contribution',()=>{
 const e=new ViewerEngine({maxRecords:1});e.encode([1,0,1,0],[10,10],{tag:'old'});
 const before=[...e.re];e.encode([0,1,0,1],[50,50],{tag:'new'});
 assert.deepEqual(e.records.map(r=>r.tag),['new']);assert.equal(e.payloads.size,1);assert.equal(e.patterns.size,1);
 for(let r=2;r<18;r++)for(let c=2;c<18;c++)assert.equal(e.re[r*64+c],before[r*64+c]);
});
test('invalid numeric text is rejected without coercing non-finite values',()=>{
 for(const s of ['', 'NaN','1, Infinity','1, nope'])assert.equal(parseNumericInput(s),null);
 assert.deepEqual(parseNumericInput('1, -2 0.25'),[1,-2,.25]);
 const e=new ViewerEngine();assert.throws(()=>e.encode([Infinity],[20,20]));assert.equal(e.records.length,0);
});
test('zero noise copies input and seeded noise is reproducible',()=>{
 const x=[1,2,3];const y=addNoise(x,0,7);assert.deepEqual(y,x);assert.notEqual(y,x);assert.deepEqual(addNoise(x,.2,7),addNoise(x,.2,7));
});
