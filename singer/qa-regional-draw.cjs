/* Automated coverage for preference-based drawing without changing identity records. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const mod=require("./regional-draw.js");
const root=__dirname,policy=JSON.parse(fs.readFileSync(path.join(root,"regional-draw-policy.json"),"utf8"));
assert.equal(policy.schemaVersion,1);
assert(policy.mainlandHongkongMaxShareForShortRounds>0&&policy.mainlandHongkongMaxShareForShortRounds<=.15);
assert(policy.weights.hongkong<policy.weights.default);
assert(policy.weights.mainland<policy.weights.default);
assert.equal(new Set(policy.lowFrequencyNames.mainland).size,policy.lowFrequencyNames.mainland.length);
assert.equal(new Set(policy.lowFrequencyNames.hongkong).size,policy.lowFrequencyNames.hongkong.length);
const overlap=policy.lowFrequencyNames.mainland.filter(name=>policy.lowFrequencyNames.hongkong.includes(name));
assert.deepEqual(overlap,[],"A person must not be in both low-frequency markets");
const allRoster=[
 ["roster.json","singers"],["actors-roster.json","actors"],["variety-roster.json","variety"]
].flatMap(([file,key])=>JSON.parse(fs.readFileSync(path.join(root,file),"utf8"))[key]);
const canonical=new Map(allRoster.map(q=>[q.name,q.id]));
for(const [kind,names] of Object.entries(policy.lowFrequencyNames)){
 for(const name of names)assert(canonical.has(name),"Unknown regional classification entry: "+kind+"/"+name);
}
assert.equal(mod.regionOf({id:"s197",name:"劉德華"},policy),"hongkong");
assert.equal(mod.regionOf({id:"s271",name:"那英"},policy),"mainland");
assert.equal(mod.regionOf({id:"s001",name:"周杰倫"},policy),"default");
assert.equal(mod.regionOf({id:"kr3_20261108_08",name:"金世正"},policy),"korea");
// Weighted sampling is randomized but never permits a short-round surplus
// while enough unseen people from other regions exist.
const HK=policy.lowFrequencyNames.hongkong.slice(0,45).map((name,i)=>({id:"hk"+i,name}));
const CN=policy.lowFrequencyNames.mainland.slice(0,25).map((name,i)=>({id:"cn"+i,name}));
const TW=Array.from({length:70},(_,i)=>({id:"tw"+i,name:"臺灣測試藝人"+i}));
const KR=Array.from({length:15},(_,i)=>({id:"kr3_20261108_"+String(i+40).padStart(2,"0"),name:"韓國測試藝人"+i}));
const universe=[...HK,...CN,...TW,...KR];
const regionById=new Map(universe.map(q=>[q.id,mod.regionOf(q,policy)]));
const lowCount=deck=>deck.filter(id=>["hongkong","mainland"].includes(regionById.get(id))).length;
function rng(seed){return ()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};}
for(let i=1;i<=300;i++){
 const deck10=mod.makeDeck(universe,[],10,policy,rng(i));
 const deck20=mod.makeDeck(universe,[],20,policy,rng(i+5000));
 assert.equal(deck10.length,10);assert.equal(new Set(deck10).size,10);
 assert.equal(deck20.length,20);assert.equal(new Set(deck20).size,20);
 assert(lowCount(deck10)<=1,"Too many mainland/HK faces in 10-question round");
 assert(lowCount(deck20)<=2,"Too many mainland/HK faces in 20-question round");
}
const full=mod.makeDeck(universe,[],universe.length,policy,rng(200));
assert.equal(full.length,universe.length);
assert.equal(new Set(full).size,universe.length);
assert(lowCount(full)===HK.length+CN.length,"All pool must include Hong Kong and mainland celebrities");
// Every available unseen question takes precedence over repeats, even when
// the only unseen candidates happen to be from a lower-frequency group.
const someUnseen=[HK[0],HK[1],HK[2],TW[0]];
const someSeen=universe.map(x=>x.id).filter(id=>!someUnseen.some(q=>q.id===id));
const chosen=mod.makeDeck(universe,someSeen,10,policy,rng(42));
assert.deepEqual(new Set(chosen.slice(0,4)),new Set(someUnseen.map(x=>x.id)),"Unseen people must be scheduled first");
const repeated=mod.makeDeck(universe,universe.map(q=>q.id),10,policy,rng(42));
assert.deepEqual(repeated,universe.slice(0,10).map(q=>q.id),"Exhausted roster should revisit least-recently seen first");
const sample=mod.makeDeck(universe,[],10,policy,()=>.5);
assert.equal(new Set(sample).size,10,"Equal random keys must still produce unique results");
// Safety: eligible pool must never be reduced by regional preferences.
for(const r of ["hongkong","mainland","korea","default"])assert(universe.some(q=>mod.regionOf(q,policy)===r));
console.log("PASS: classified name list, short round caps, unbiased fallback, all-questions pool, shared seen history");
