
/*
 * Ninety one-off locale compositions. No original pilot scene is reused.
 * Each of the 90 data rows has a different main subject silhouette and
 * a separately planned set of five clue motifs.
 */
(function(){
const categories=Object.create(null);
const pools={
  sky:['bird','cloud','flag','planet','star','snow','wing','clock','radio','poster','compass'],
  middle:['sign','window','plaque','clockface','clock','lantern','lamp','gear','note','poster','tile','stripe','lock','ribbon','radio','glass','book'],
  ground:['leaf','flower','bottle','glass','cup','fish','shell','basket','crate','fruit','candy','flowerpot','ticket','chair','battery','plaque','gear','flag','book','compass'],
  any:['sign','plaque','window','flag','clock','poster','lantern','note','flower','leaf','ticket','gear','book','glass','basket','star']
};
const regionForType={
 cloud:'sky',bird:'sky',star:'sky',planet:'sky',snow:'sky',wing:'sky',
 window:'middle',sign:'middle',plaque:'middle',clock:'middle',clockface:'middle',
 poster:'middle',tile:'middle',stripe:'middle',gear:'middle',radio:'middle',
 lock:'middle',note:'middle',lamp:'middle',lantern:'middle',
 fish:'ground',flower:'ground',leaf:'ground',flowerpot:'ground',shell:'ground',
 cup:'ground',basket:'ground',crate:'ground',fruit:'ground',bottle:'ground',
 candy:'ground',glass:'ground',chair:'ground',battery:'ground'
};
function makeRand(seed){
 let n=seed|0||1;
 return ()=>{n^=n<<13;n^=n>>>17;n^=n<<5;return(n>>>0)/4294967296;};
}
function shuffle(items,rand){
 const a=items.slice();
 for(let i=a.length-1;i>0;i--){const k=Math.floor(rand()*(i+1));[a[i],a[k]]=[a[k],a[i]];}
 return a;
}
function points(rand){
 // Reject candidates that would cause visual/click hotspots to overlap.
 let all=[],tryCount=0;
 while(all.length<21 && tryCount++<9000){
  const x=58+rand()*682,y=63+rand()*347;
  if(all.every(p=>Math.hypot(p.x-x,p.y-y)>102))all.push({x,y,region:y<170?'sky':y<285?'middle':'ground'});
 }
 if(all.length<17)throw new Error('insufficient scenic positions');
 return all;
}
function choose(types,positions,rand){
 let chosen=[],pool=positions.slice(),count=0;
 for(const type of types){
  const region=regionForType[type]||'any';
  const compatible=pool.filter(p=>region==='any'||p.region===region);
  const arr=compatible.length?compatible:pool;
  if(!arr.length)throw new Error('clue locations exhausted');
  const pos=arr[Math.floor(rand()*arr.length)];
  chosen.push({type,...pos});
  pool.splice(pool.indexOf(pos),1);
 }
 return {chosen,remaining:shuffle(pool,rand)};
}
function accentFor(cfg,j){
 return [cfg.accent,'#f5dba5','#75ada8','#c1a0bf','#e6a68e','#abc7d1'][j%6];
}
function ornament(cfg,j,random){
 const c=cfg.accent,x=j%2?602:67,y=j%4?152:98;
 // Large bold distractions are intentionally identical in both pictures.
 let s=G('translate('+x+' '+y+') rotate('+((j%5)*7-15)+')',
    E(0,0,40,35,c,'opacity=".72"')+
    star(-5,-7,9,'#ffeed7')+
    repeat(5,i=>C(-28+i*14,20+(i%2)*8,3.5,'#fff4dc')));
 if(j%3===0)s+=G('translate('+(j%2?82:680)+' 267)',P('M-39 20L0 -37L39 20Z',c)+C(0,7,9,'#fff3ca'));
 if(j%4===0)s+=G('translate(695 368)',E(0,0,43,22,'#e9c58c')+T(0,2,'✦',27,'#8f858c'));
 return s;
}

function scenicPatch(kind,x,y,accent,changed,seed,scale=1){
 const gold='#ffe5b9',ink='#526679',ice='#e1f3e5';
 let art='';
 switch(kind%9){
 case 0: // window grille built into the façade
  art=R(-32,-25,64,49,'#739da4','rx="4" stroke="'+gold+'" stroke-width="4"')+
  L(0,-25,0,24,gold,3)+L(-32,changed?7:0,32,changed?7:0,gold,3);break;
 case 1: // old painted masonry — a shortened painted seam
  art=R(-30,-20,60,42,accent,'opacity=".53"')+L(-28,-2,changed?13:29,-2,gold,4)+L(-5,-20,-5,-2,gold,2);break;
 case 2: // placard, frequently loud but often unchanged
  art=R(-38,-21,76,40,'#455d72','rx="5"')+R(-34,-17,68,32,accent)+T(0,-1,changed?'08':'03',20,gold);break;
 case 3: // architectural flourish — two or three rivets
  art=R(-35,-11,70,23,'#aa8f82','rx="6"')+repeat(changed?2:3,i=>C(-22+i*22,0,6,gold));break;
 case 4: // railing with a missing upright
  art=L(-34,-21,34,-21,ink,5)+L(-34,20,34,20,ink,5)+repeat(4,i=>i===2&&changed?'':L(-28+i*18,-20,-28+i*18,20,ice,3));break;
 case 5: // emblem in the main subject
  art=C(0,0,28,accent)+C(0,0,19,gold)+T(0,1,changed?'✦':'★',22,ink);break;
 case 6: // shadow/reflection goes the opposite way
  art=E(0,12,33,12,'#769a9d','opacity=".7"')+
       P(changed?'M-6 16L26 1L22 21Z':'M-6 16L-26 1L-22 21Z',ice,'opacity=".9"');break;
 case 7: // lamp or far-off building fixture
  art=L(0,-28,0,-18,ink,3)+P('M-22 -18L22 -18L31 9L-31 9Z',accent)+
       C(changed?8:0,10,8,gold)+L(-28,13,28,13,ice,2);break;
 default: // compass/hand orientation 
  art=C(0,0,28,ice)+C(0,0,24,accent)+L(0,0,0,-18,ink,3)+
       L(0,0,changed?20:-20,changed?-3:9,ink,4)+C(0,0,3,ink);
 }
 return G('translate('+x.toFixed(2)+' '+y.toFixed(2)+') scale('+scale.toFixed(3)+')',art);
}
function structuralSpots(j,cfg,viewpoint,existing,rand,count){
 const results=[];
 const heroLocations=[
  {x:viewpoint.x+80*viewpoint.scale,y:viewpoint.y+62*viewpoint.scale},
  {x:viewpoint.x+165*viewpoint.scale,y:viewpoint.y+72*viewpoint.scale},
  {x:viewpoint.x+111*viewpoint.scale,y:viewpoint.y+125*viewpoint.scale}
 ];
 const backdropLocations=[
  {x:95+(j%3)*17,y:102+(j%5)*9},
  {x:695-(j%4)*13,y:206+(j%3)*23},
  {x:76+(j%4)*18,y:360-(j%3)*25},
  {x:654-(j%3)*21,y:82+(j%4)*8},
  {x:583+(j%3)*17,y:373-(j%4)*11}
 ];
 const activeCenters=existing.map(p=>({x:p.x,y:p.y}));
 for(let k=0;k<count;k++){
  const desiredHero=(j%5===1||j%5===2||j%5===4)&&(k===0||j%5===2);
  const pool=shuffle(desiredHero?heroLocations:backdropLocations,rand);
  pool.sort((a,b)=>{
   const da=Math.min(...activeCenters.map(p=>Math.hypot(a.x-p.x,a.y-p.y)),9999);
   const db=Math.min(...activeCenters.map(p=>Math.hypot(b.x-p.x,b.y-p.y)),9999);
   return db-da;
  });
  const loc=pool[0];
  if(!loc)throw Error('no structural anchor');
  activeCenters.push(loc);
  const index=j*5+k+(desiredHero?2:0),sc=desiredHero?viewpoint.scale:1;
  results.push([loc.x,loc.y,33,b=>scenicPatch(index,loc.x,loc.y,cfg.accent,!!b,cfg.seed,sc)]);
 }
 return results;
}

function create(cfg,j,cluePlan){
 const rand=makeRand(cfg.seed+93);
 const locs=points(rand);
 const structuralCount=[2,2,2,1,1][j%5];
 const {chosen,remaining}=choose(cluePlan.slice(0,5-structuralCount),locs,rand);
 const colors=spotColors(cfg);
 // Static props and actual changes use the same visual system.
 // Large vivid props may be false clues.
 const usedColorCount=Object.create(null);
 const flags=shuffle([1,0,0,0,1,0,0,0,0,0,0,0,0,0,0],rand);
 const fixed=remaining.map((p,i)=>{
  const pool=p.region==='sky'?pools.sky:p.region==='middle'?pools.middle:pools.ground;
  let type=pool[Math.floor(rand()*pool.length)];
  if(i===0)type=['sign','lantern','poster','flag','plaque'][j%5];
  let sc=flags[i]?1.25+rand()*.12:.8+rand()*.26;
  return {type,...p,scale:sc,rotation:(rand()-.5)*19,color:colors[Math.floor(rand()*colors.length)]};
 });
 const active=chosen.map((p,i)=>({
  ...p,scale:.93+rand()*.24,rotation:(rand()-.5)*14,
  color:colors[Math.floor(rand()*colors.length)],caption:p.type==='sign'?cfg.sign:''
 }));
 const viewpoint={
  x:228+(j%5)*18+(rand()-.5)*44,
  y:144+(j%4)*10,
  scale:1.15+(j%3)*.11
 };
 // The independently drawn silhouette is unique to this subject.
 const hero=HERO[cfg.hero];
 if(typeof hero!=='function')throw new Error('Missing focal illustration '+cfg.hero);
 const oldBase=artistBackground(cfg,j);
 const focal=G('translate('+viewpoint.x.toFixed(2)+' '+viewpoint.y.toFixed(2)+') scale('+viewpoint.scale.toFixed(3)+')',hero(cfg.accent));
 const identicalDecor=ornament(cfg,j,rand);
 const fixedArt=fixed.map(p=>detailG(p.type,j,p.color,false,p.x.toFixed(1),p.y.toFixed(1),p.scale,p.rotation,p.type==='sign'?cfg.sign:'')).join('');
 const heading=R(291,7,426,39,'#243e50','rx="9" opacity=".88"')+T(501,26,cfg.sign,23,'#fbe5bf');
 const baseSVG=oldBase+focal+identicalDecor+fixedArt+heading;
 const diffs=active.map(p=>[
    p.x,p.y,31,
    b=>detailG(p.type,j,p.color,!!b,p.x.toFixed(1),p.y.toFixed(1),p.scale,p.rotation,p.caption)
 ]);
 diffs.push(...structuralSpots(j,cfg,viewpoint,active,rand,structuralCount));
 if(diffs.length!==5)throw Error('Stage does not contain five differences: '+cfg.name);
 register(cfg.name,'觀察整個場景：醒目物件不一定是答案。',()=>baseSVG,diffs);
}
if(FULL_SCENES.length!==90||CLUE_PLANS.length!==90)throw Error('Missing full-game data');
// Interleave nine thematic families so two consecutive stages never share a repeated backdrop family.
for(let j=0;j<90;j++){const src=Math.floor(j/9)+(j%9)*10;create(FULL_SCENES[src],j,CLUE_PLANS[src]);}
})();
