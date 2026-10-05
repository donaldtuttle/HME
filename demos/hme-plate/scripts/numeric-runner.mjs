import fs from 'node:fs';import {ViewerEngine} from '../src/model.js';
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
const output=cases.map(c=>{
 const m=new ViewerEngine({useHannWindow:c.hann});
 c.inputs.forEach((x,i)=>m.encode(x,c.positions[i],{tag:`item-${i}`}));
 if(c.erase)m.eraseField();
 const r=m.retrieve(c.positions[0],{query:c.query,topK:c.inputs.length,threshold:c.threshold,radius:4});
 return {fieldRe:[...m.re],fieldIm:[...m.im],tags:r.hits.map(h=>h.tag),scores:r.hits.map(h=>[h.baseScore,h.distanceScore,h.queryScore,h.patternScore]),outcome:r.outcome,decoded:r.decodedRe,surface:r.surfaceMag};
});
process.stdout.write(JSON.stringify(output));
