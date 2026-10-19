
// Original scalable vector illustration primitives: no network assets, no image downloads.
const V={
 R:(x,y,w,h,c,ex='')=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="'+c+'" '+ex+'/>',
 C:(x,y,r,c,ex='')=>'<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+c+'" '+ex+'/>',
 E:(x,y,rx,ry,c,ex='')=>'<ellipse cx="'+x+'" cy="'+y+'" rx="'+rx+'" ry="'+ry+'" fill="'+c+'" '+ex+'/>',
 P:(d,c,ex='')=>'<path d="'+d+'" fill="'+c+'" '+ex+'/>',
 L:(x,y,a,b,c,w=2,ex='')=>'<path d="M'+x+' '+y+'L'+a+' '+b+'" fill="none" stroke="'+c+'" stroke-width="'+w+'" stroke-linecap="round" '+ex+'/>',
 T:(x,y,t,sz,c)=>'<text x="'+x+'" y="'+y+'" font-size="'+sz+'" font-family="system-ui,sans-serif" text-anchor="middle" font-weight="800" fill="'+c+'">'+t+'</text>'
};
const {R,C,E,P,L,T}=V;
const COLORS={cream:'#fff4db',ink:'#263347',gold:'#ffc975',pink:'#f39ba9',mint:'#89d1b8',blue:'#82bad9',wood:'#a66d63',white:'#fffdf5'};
const COL=COLORS;
function rng(seed){let a=(seed|0)||1;return ()=>{a^=a<<13;a^=a>>>17;a^=a<<5;return (a>>>0)/4294967296;};}
function propArt(type,changed,color,token=0){
 const w=COL.cream,k=COL.ink,g=COL.gold,p=COL.pink,m=COL.mint,b=COL.blue,wd=COL.wood;
 let s='';
 switch(type){
 case 'flower':case 'rose':
   s+=L(14,12,14,27,k,2.3)+E(10,21,5,2.5,m,'transform="rotate(-28 10 21)"')+E(18,22,5,2.5,m,'transform="rotate(26 18 22)"');
   for(let i=0;i<6;i++){let a=i*Math.PI/3;s+=C(14+6*Math.cos(a),9+6*Math.sin(a),4,type==='rose'?p:color);}
   s+=C(14,9,3.3,g)+(changed?C(20,10,2,w):C(8,11,2,w));break;
 case 'leaf':case 'tree':case 'palm':case 'seaweed':
   s+=L(14,6,14,27,wd,2.8)+P('M14 5Q-3 12 9 20Q20 18 14 5',m)+P('M14 8Q31 8 22 21Q13 20 14 8',color);
   s+=changed?L(14,15,23,19,w,1.2):L(14,15,8,17,w,1.2);break;
 case 'book':case 'notebook':case 'ticket':case 'poster':
   s+=R(4,3,20,23,color,'rx="2"')+R(7,6,15,17,w,'rx="1"')+L(9,11,19,11,k,1.4)+L(9,15,19,15,k,1.2)+(changed?L(9,19,14,19,k,1):L(9,19,19,19,k,1));break;
 case 'clock':
   s+=C(14,14,12,w)+C(14,14,10,color)+C(14,14,7,w)+L(14,14,14,8,k,1.8)+L(14,14,changed?19:18,changed?15:19,k,2)+C(14,14,1.7,k);break;
 case 'cup':case 'coffee':case 'hotdrink':case 'drink':
   s+=P('M4 9L23 9L21 23Q15 27 7 23Z',color)+P('M22 12Q31 10 26 19L22 21', 'none','stroke="'+w+'" stroke-width="2.5"')+E(13.5,10,9,2.4,w);
   s+=changed?L(12,4,10,0,w,1.3):L(17,4,19,0,w,1.3);break;
 case 'fish':case 'bird':case 'butterfly':case 'plane':
   if(type==='fish'){s+=E(13,14,9,6,color)+P('M6 14L1 8L1 20Z',m)+C(18,12,1.4,k)+L(11,14,11,18,w,1.3)+(changed?'':L(14,14,14,18,w,1));}
   else if(type==='bird'){s+=E(14,16,10,5.7,color)+C(20,11,4,color)+P('M24 11L28 13L24 15Z',g)+C(22,10,1,k)+(changed?L(8,10,14,12,w,2):L(9,15,15,12,w,2));}
   else if(type==='plane'){s+=P('M2 16L26 4L19 26L15 18Z',color)+L(15,18,changed?20:23,10,w,1.5);}
   else{s+=E(9,10,6,8,color)+E(19,10,6,8,m)+E(9,22,5,5,m)+E(19,22,5,5,color)+L(14,8,14,25,k,2)+(changed?C(10,9,2,w):C(18,9,2,w));}break;
 case 'bottle':case 'potion':case 'detergent':case 'can':
   s+=R(10,2,8,5,k)+R(6,8,16,19,color,'rx="4"')+R(8,13,12,9,w,'rx="2"')+(changed?T(14,21,'✦',8,k):T(14,21,'●',7,k));break;
 case 'lantern':case 'lamps':case 'lamp':case 'candle':case 'bell':
   s+=L(14,0,14,6,k,2)+P('M9 6Q14 1 19 6L23 20Q14 27 5 20Z',color)+R(9,9,10,10,w,'rx="2"')+L(8,14,20,14,k,1.2)+(changed?C(14,12,2,p):C(14,17,2,p));break;
 case 'sign':case 'screen':case 'neon':case 'canvas':
   s+=R(2,3,24,21,k,'rx="3"')+R(4,5,20,17,color,'rx="2"')+T(14,19,changed?'✦':'★',13,w);break;
 case 'gear':case 'trainwheel':
   s+=C(14,14,12,k)+C(14,14,8,color)+C(14,14,4,w);
   for(let i=0;i<(changed?7:8);i++){let a=i*Math.PI/4;s+=R(12+12*Math.cos(a),12+12*Math.sin(a),4,4,color);}break;
 case 'apple':case 'fruit':case 'grape':case 'banana':case 'carrot':case 'seed':
   s+=E(14,16,10,9,color)+L(14,8,16,3,k,2)+E(20,6,5,2.5,m,'transform="rotate(-27 20 6)"')+(changed?C(11,16,1.8,w):C(19,16,1.8,w));break;
 case 'basket':case 'crate':case 'box':case 'suitcase':case 'bag':
   s+=R(3,11,22,16,color,'rx="2"')+P('M7 11Q7 0 14 0Q21 0 21 11','none','stroke="'+k+'" stroke-width="2.4"')+L(4,17,24,17,w,1.5)+(changed?L(10,11,10,27,k,1.1):L(18,11,18,27,k,1.1));break;
 case 'umbrella':case 'fan':
   s+=P('M1 14Q6 -3 14 2Q23 -3 27 14Z',color)+L(14,13,14,25,k,2)+P('M14 25Q18 29 20 24','none','stroke="'+k+'" stroke-width="2"')+(changed?L(8,10,10,5,w,1.2):L(19,10,17,5,w,1.2));break;
 case 'plant':case 'pot':
   s+=P('M6 16L22 16L20 27L8 27Z',wd)+L(14,16,14,2,k,1.8)+P('M14 12Q-1 2 5 0Q16 1 14 12',m)+P('M14 12Q29 1 25 0Q15 1 14 12',color)+(changed?C(14,7,2,g):C(15,11,2,g));break;
 case 'mushroom':
   s+=R(10,13,8,13,w,'rx="3"')+P('M2 15Q4 0 14 2Q25 0 26 15Z',color)+C(changed?8:11,11,2,w)+C(19,9,2.2,w);break;
 case 'star':case 'starfish':case 'snowflake':case 'moon':case 'sun':case 'cloud':
   if(type==='cloud')s+=C(10,17,7,w)+C(16,13,9,w)+C(22,19,6,w)+R(6,18,21,6,w);
   else if(type==='moon')s+=C(14,14,11,g)+C(changed?19:21,9,10,k);
   else if(type==='sun')s+=C(14,14,9,g)+L(changed?2:4,3,5,6,g,2)+L(23,4,20,7,g,2);
   else if(type==='snowflake'){for(let i=0;i<6;i++){let a=i*Math.PI/3;s+=L(14,14,14+12*Math.cos(a),14+12*Math.sin(a),w,2);}s+=C(14,14,changed?4:2,color);}
   else{s+=P('M14 1L18 11L27 11L20 17L22 27L14 21L6 27L8 17L1 11L10 11Z',color)+(changed?C(14,13,2,w):C(14,17,2,w));}break;
 case 'bubble':case 'pearl':
   s+=C(14,14,11,color,'opacity=".8"')+C(14,14,9,'none','stroke="'+w+'" stroke-width="1"')+C(changed?9:11,10,3,w);break;
 case 'shell':
   s+=P('M2 22Q1 2 14 3Q27 2 26 22Z',color)+L(14,5,14,22,w,1.2)+L(9,8,6,22,w,1)+(changed?L(19,8,21,22,w,1):'');break;
 case 'boat':case 'anchor':case 'bridge':
   s+=P('M2 17L26 17L21 25L7 25Z',color)+L(14,17,14,1,k,1.7)+P('M14 3L14 15L24 15Z',w)+(changed?C(14,19,2.5,g):C(11,19,2.5,g));break;
 case 'chair':case 'bench':case 'log':case 'tool':
   s+=R(5,5,19,13,color,'rx="2"')+R(3,17,22,4,wd)+L(8,21,7,27,k,2)+L(21,21,22,27,k,2)+(changed?L(8,11,20,11,w,1.4):L(8,14,20,14,w,1.4));break;
 case 'cake':case 'cupcake':case 'donut':case 'candy':case 'lollipop':case 'icecream':case 'bread':case 'noodle':
   s+=R(5,13,18,13,color,'rx="3"')+E(14,13,10,5,w)+C(14,6,4,p)+(changed?C(8,14,1.5,g):C(20,14,1.5,g))+L(6,22,22,22,wd,1.5);break;
 case 'bowl':case 'plate':case 'egg':case 'spoon':case 'chopsticks':
   s+=E(14,13,12,8,w)+P('M3 14Q5 29 14 27Q25 28 26 14Z',color)+E(14,11,4.5,g)+(changed?C(19,13,1.5,p):C(8,13,1.5,p));break;
 case 'cat':case 'dog':case 'owl':case 'frog':case 'monkey':case 'paw':
   s+=C(14,16,10,color)+P('M5 12L3 2L12 8Z',color)+P('M17 7L26 2L24 12Z',color)+C(10,16,1.5,k)+C(18,16,1.5,k)+P('M12 21L16 21L14 23Z',p)+(changed?L(5,20,9,22,w,1):L(19,22,23,20,w,1));break;
 case 'robot':case 'console':case 'gamepad':case 'radio':
   s+=R(3,6,22,19,color,'rx="4"')+R(7,9,14,9,k,'rx="2"')+C(11,13,2,w)+C(18,13,2,w)+L(14,6,14,2,k,1.8)+C(14,2,2,g)+(changed?C(10,22,2,p):C(18,22,2,p));break;
 case 'record':case 'disc':case 'music':case 'headphone':case 'violin':
   s+=C(14,14,12,k)+C(14,14,8,color)+C(14,14,3.5,w)+C(14,14,1,k)+(changed?L(5,8,8,10,w,1.6):L(20,20,23,17,w,1.6));break;
 case 'camera':case 'clapper':case 'battery':
   s+=R(2,7,24,18,k,'rx="3"')+R(7,4,9,4,color)+C(14,16,8,color)+C(14,16,4.5,w)+C(14,16,2,k)+(changed?C(23,10,1.8,p):C(5,10,1.8,p));break;
 case 'planet':case 'rocket':case 'antenna':
   s+=C(14,14,9,color)+E(14,15,13,5,'none','stroke="'+w+'" stroke-width="2" transform="rotate(-23 14 15)"')+(changed?C(11,10,2,w):C(17,16,2,w));break;
 case 'puddle':case 'water':case 'steam':
   s+=E(14,19,13,6,color)+E(14,19,10,3.5,b)+L(7,19,changed?17:13,19,w,1.3);break;
 case 'flag':case 'shield':case 'hat':case 'helmet':case 'mask':
   s+=L(8,1,8,28,k,2)+P('M9 3L26 5L20 14L9 12Z',color)+(changed?C(16,8,2,w):C(20,10,2,w));break;
 case 'balloon':case 'ball':case 'heart':
   s+=C(14,12,10,color)+L(14,22,14,28,k,1.5)+(changed?C(10,9,2,w):C(18,9,2,w));break;
 case 'carrot': case 'grape': break;
 default:
   s+=R(4,4,20,20,color,'rx="5"')+C(14,14,7,w)+T(14,18,changed?'✦':'★',12,k);
 }
 // Small, context-dependent secondary details increase visual richness without adding unrelated differences.
 return '<g>'+s+'</g>';
}
function drawProp(o,changed,p){
 return '<g transform="translate('+o.x.toFixed(2)+' '+o.y.toFixed(2)+') rotate('+o.rot+') scale('+o.scale.toFixed(3)+')" filter="url(#softShadow)">'+propArt(o.type,changed,p,o.idx)+'</g>';
}
