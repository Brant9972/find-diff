/* Region-aware quiz order. No one is removed; only short-round odds change. */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 if(root)root.FaceStarRegionDraw=api;
})(typeof window!=="undefined"?window:globalThis,function(){
 "use strict";
 function regionOf(q,policy){
  // Market is explicit per ID. Only uncatalogued new IDs use legacy name fallbacks.
  const market=policy?.primaryMarketsById?.[q.id] ?? q.primaryMarket;
  if(typeof market==="string"&&market&&market!=="unverified")return market;
  const lists=policy&&policy.lowFrequencyNames||{};
  if(Array.isArray(lists.mainland)&&lists.mainland.includes(q.name))return "mainland";
  if(Array.isArray(lists.hongkong)&&lists.hongkong.includes(q.name))return "hongkong";
  if(Array.isArray(policy?.koreanIdPrefixes)&&policy.koreanIdPrefixes.some(p=>q.id.startsWith(p)))return "korea";
  return "default";
 }
 function low(region){return region==="mainland"||region==="hongkong";}
 function weightedOrder(items,policy,rng=Math.random){
  const weights=policy&&policy.weights||{};
  return items.map(q=>{
   const region=regionOf(q,policy);
   const configured=Number(weights[region]??weights.default??1);
   const weight=Number.isFinite(configured)&&configured>0?configured:1;
   const u=Math.max(1e-12,Math.min(1-1e-12,Number(rng())));
   return {id:q.id,region,key:-Math.log(u)/weight};
  }).sort((a,b)=>a.key-b.key).map(({id,region})=>({id,region}));
 }
 function makeDeck(items,history,limit,policy,rng=Math.random){
  const eligible=new Set(items.map(q=>q.id)),seen=new Set(history);
  const unseen=weightedOrder(items.filter(q=>!seen.has(q.id)),policy,rng);
  const wanted=Math.min(limit,unseen.length),allItems=limit>=items.length;
  const share=Number(policy?.mainlandHongkongMaxShareForShortRounds);
  const useCap=!allItems&&Number.isFinite(share)&&share>=0&&share<=1;
  const maxLow=useCap?Math.floor(limit*share):Infinity;
  const chosen=[],deferred=[];let selectedLow=0;
  for(const entry of unseen){
   if(chosen.length>=wanted)break;
   if(useCap&&low(entry.region)&&selectedLow>=maxLow){deferred.push(entry);continue;}
   chosen.push(entry.id);
   if(low(entry.region))selectedLow++;
  }
  // If the remaining unseen pool has mostly HK/Mainland people, show those
  // rather than repeating people who have already appeared.
  for(const entry of deferred){
   if(chosen.length>=wanted)break;
   chosen.push(entry.id);
  }
  const older=history.filter(id=>eligible.has(id));
  return [...chosen,...older].slice(0,limit);
 }
 return {regionOf,weightedOrder,makeDeck};
});
