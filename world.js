
// Scene director: 50 hand-illustrated landmarks + independent props + varied backdrops.
// Each theme appears only twice across 100 stages, with a different layout on its return.
function sceneBackground(cfg,alt,themeIndex){
 const dark=['night','space','city','theater','interior','studio'].includes(cfg.zone);
 const sky=dark?'#293550':['#b5d6d8','#b3d4c9','#edc7c8','#acc7e7','#dbd7b0'][themeIndex%5];
 let s='<defs><linearGradient id="sceneSky" x1="0" y1="0" x2="1" y2="1"><stop stop-color="'+sky+'"/><stop offset="1" stop-color="'+(dark?'#59607d':'#f7dbc4')+'"/></linearGradient><filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1.5" stdDeviation=".8" flood-opacity=".24"/></filter></defs>'+R(0,0,480,280,'url(#sceneSky)');
 const zone=cfg.zone;
 const hor=alt?195:199;
 const wall=()=>R(0,30,480,170,dark?'#444559':'#e6cfb7','opacity=".53"');
 const floor=()=>R(0,hor,480,280-hor,dark?'#5f5864':'#bea28a');
 if(['interior','studio','food','museum','theater','factory'].includes(zone)){
  s+=wall()+floor();
  s+=R(20,42,122,85,dark?'#55677b':'#c6d6c9','rx="5"')+R(26,48,110,73,'#a8d8dc','rx="3"');
  s+=L(80,47,80,121,'#8a8c83',4)+L(26,84,136,84,'#8a8c83',3);
  s+=R(334,53,124,72,'#c2a996','rx="4"')+[355,390,425].map(x=>R(x,61,20,57,'#8d7a73')).join('');
  s+=R(0,196,480,9,dark?'#454454':'#9d8b7d');
  s+=L(0,238,480,238,dark?'#7e7488':'#d3b9aa',1);
 }else if(['market','city','rail','night','festival'].includes(zone)){
  s+=R(0,139,480,141,zone==='night'?'#534961':'#9fa5a3');
  for(let i=0;i<7;i++){let x=i*85-15,h=65+(i*37+themeIndex*9)%66;
   s+=R(x,161-h,76,h,['#738995','#887e92','#789b9b','#a0a2a5'][i%4]);
   for(let k=0;k<3;k++)s+=R(x+11+k*19,172-h,11,18,dark?'#e7bf87':'#d9e2cc','opacity=".8"');
  }
  s+=R(0,205,480,75,zone==='night'?'#504458':'#a39b8d');
  s+=L(0,239,480,239,'#f3eee2',2,'stroke-dasharray="28 22" opacity=".7"');
 }else if(['forest','greenhouse','garden','mountain','sky','desert','snow'].includes(zone)){
  s+=C(alt?405:75,51,27,zone==='snow'?'#fafcff':'#fff1ae','opacity=".74"');
  s+=P('M0 205Q100 85 195 179Q311 113 480 198L480 280L0 280Z',zone==='desert'?'#d6b08a':zone==='snow'?'#d5e7ee':'#8dba98');
  s+=P('M0 226Q110 151 260 216Q376 148 480 220L480 280L0 280Z',zone==='desert'?'#e4c396':zone==='snow'?'#f0f2ed':'#71a78c');
  if(zone==='forest'||zone==='greenhouse'||zone==='garden'){for(let i=0;i<8;i++){let x=13+i*68+(alt?13:0);s+=L(x,143,x,221,'#7f7562',7)+C(x,144,29,['#5d987e','#6aa48c','#85b69a'][i%3]);}}
  if(zone==='snow')for(let i=0;i<30;i++)s+=C((i*79+themeIndex*13)%480,(i*61+47)%202,2,'#fff','opacity=".65"');
 }else if(['coast','ocean'].includes(zone)){
  s+=R(0,145,480,135,zone==='ocean'?'#3889a2':'#6ab5c2');
  s+=P('M0 206Q36 196 72 206T144 206T216 206T288 206T360 206T432 206L480 206L480 280L0 280Z',zone==='ocean'?'#207c91':'#82c6c0');
  for(let i=0;i<21;i++)s+=L((i*91)%470,162+(i*23)%99,(i*91)%470+13,162+(i*23)%99,'#d5eef0',1.8,'opacity=".47"');
  if(zone==='coast')s+=P('M0 252Q133 212 241 251T480 246L480 280L0 280Z','#ddc9a5');
  if(zone==='ocean')for(let i=0;i<22;i++)s+=C((i*87)%480,(i*47)%230+19,i%3+1,'#dbf5f6','opacity=".42"');
 }else if(zone==='space'){
  s+=R(0,0,480,280,'#172844','opacity=".78"');
  for(let i=0;i<70;i++)s+=C((i*97+themeIndex*29)%480,(i*61+themeIndex*9)%235,i%7===0?2:1,'#d4ebff','opacity=".73"');
  s+=P('M0 253Q130 197 261 250T480 246L480 280L0 280Z','#747e9e');
  s+=C(alt?68:414,69,40,'#bdcbe2');
  s+=C(alt?76:422,55,11,'#8ba8bf','opacity=".54"');
 }else{
  s+=floor()+R(0,60,480,128,'#d2c6ae')+R(0,192,480,14,'#887a78');
 }
 if(zone==='night'){s+=C(alt?415:66,43,22,'#f2e7bf');}
 // Deliberately vary composition on the second visit, rather than only recoloring it.
 if(alt){
  s+=P('M0 246Q130 230 240 250T480 247','none','stroke="#f9f1e2" stroke-width="2" opacity=".4"');
 }
 return s;
}
const SLOTS=[
 [16,40],[91,47],[375,44],[434,41],
 [17,114],[96,121],[368,118],[433,122],
 [20,209],[98,213],[375,207],[433,208],
 [177,26],[261,23],[181,215],[285,216],
 [18,164],[433,166]
];
function makeLevel(levelNo){
 const theme=levelNo%50,alt=levelNo>=50,cfg=SCENES[theme],rand=rng((levelNo+1)*16777619);
 const slots=SLOTS.map(([x,y])=>({x,y,sort:rand()})).sort((a,b)=>a.sort-b.sort);
 const objs=[];
 for(let i=0;i<Math.min(cfg.props.length,12);i++){
  const pos=slots[i],scale=1.38+(rand()*.20);
  objs.push({type:cfg.props[i],x:Math.max(1,Math.min(439,pos.x+(rand()-.5)*8)),y:Math.max(22,Math.min(231,pos.y+(rand()-.5)*9)),rot:Math.round((rand()-.5)*10),scale,idx:i});
 }
 let target=[], tries=0;
 while(target.length<5&&tries++<1000){
  const ix=Math.floor(rand()*objs.length),o=objs[ix],cx=o.x+14*o.scale,cy=o.y+14*o.scale;
  if(target.includes(ix))continue;
  if(target.every(k=>Math.hypot(cx-(objs[k].x+14*objs[k].scale),cy-(objs[k].y+14*objs[k].scale))>65))target.push(ix);
 }
 if(target.length<5){for(let i=0;i<objs.length&&target.length<5;i++)if(!target.includes(i))target.push(i);}
 return {number:levelNo,theme,alt,cfg,objs,target};
}
function sceneSvg(level,side){
 const cfg=level.cfg;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 280" preserveAspectRatio="xMidYMid meet" role="img" aria-label="'+cfg.title+' 圖片'+side+'">';
 s+=sceneBackground(cfg,level.alt,level.theme);
 s+=drawLandmark(cfg.hero,cfg.accent,level.alt);
 // Ambience and non-target props are drawn identically in both images.
 level.objs.forEach((o,i)=>{s+=drawProp(o,side==='B'&&level.target.includes(i),cfg.accent);});
 s+='</svg>';return s;
}
