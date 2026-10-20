
/* Artistic composition library for the ninety new standalone locations.
   Each location gets its own foreground landmark in hero.js and its own detail palette.
   No clue coordinates are attached to non-difference landmarks by default. */
const FM={
  street:['#98c5ca','#dfb2a7','#817f88','#b1b6a8'],
  food:['#e4bea8','#f4d4b0','#8b766d','#ab8b7e'],
  transit:['#a2bcca','#d6d5c0','#798a8b','#abb1ab'],
  nature:['#aecbcd','#e8d5b7','#77aa8d','#b3bf9e'],
  culture:['#c5b5a8','#d0b8a1','#827777','#ac8f82'],
  work:['#a6bdc5','#d6d3c1','#7c9294','#9f9d93'],
  leisure:['#acd2ce','#e9c8af','#79a8a2','#b1afaa'],
  fantasy:['#a4a5ca','#dcb6c0','#6d789d','#8b86a6'],
  science:['#8daac5','#cfcedb','#556e89','#8fa5bb']
};
function artistBackground(cfg,j){
const colors=FM[cfg.family],seed=cfg.seed,variation=j%10,reverse=variation%3===0;
let svg=R(0,0,800,460,colors[0])+P('M0 0L800 0L800 160Q400 245 0 154Z',colors[1],'opacity=".23"');
let x0=reverse?500:38;
const family=cfg.family;
if(family==='street'){
 svg+=R(0,246,800,214,'#9c9390')+P('M0 341L800 327L800 460L0 460Z',colors[2]);
 for(let n=0;n<5;n++){let x=n*191-22+(seed%15),height=120+(n*33+seed)%90;svg+=R(x,270-height,165,height,['#a8a1a5','#8f939e','#bbb3a1'][n%3]);svg+=repeat(3,k=>R(x+18+k*45,291-height,27,31,'#d0ddd0','opacity=".75"'));}
 svg+=R(0,250,800,22,'#7e8d8b')+R(0,355,800,10,'#ecd4b5')+L(0,417,800,393,'#d3bfac',3,'stroke-dasharray="36 22"');
 svg+=repeat(4,n=>G('translate('+(35+n*232)+' '+(300+n%2*15)+')',L(0,-44,0,44,'#746263',5)+E(0,-52,17,23,['#e8b08c','#edc690','#cc8ca9'][n%3])+L(-16,-50,16,-50,'#b37e71',3)));
}else if(family==='food'){
 svg+=R(0,0,800,350,'#dec0ad')+R(0,353,800,107,'#b58e7c');
 svg+=R(26,101,231,182,'#cfddd0','rx="7"')+R(35,110,214,166,'#9ac0c5','rx="4"')+L(142,110,142,276,'#c8c5a7',7);
 svg+=R(475,81,292,240,'#a7857f','rx="11"')+R(487,95,267,217,'#f0dbc0');
 svg+=repeat(3,n=>R(499,141+n*68,243,9,'#986a65')+repeat(5,k=>E(515+k*47,126+n*68,15,10,['#e6c68e','#b97b66','#f2d0a6'][k%3])));
 svg+=R(0,331,800,27,'#9e786b')+repeat(4,i=>R(45+i*191,370,170,90,'#c69f88','rx="5"'));
}else if(family==='transit'){
 svg+=P('M0 244L121 159L244 230L379 134L540 239L710 158L800 216L800 460L0 460Z','#899e9c');
 svg+=R(0,283,800,177,'#aab0ad')+R(0,276,800,17,'#7c878d')+L(0,402,800,375,'#ede2c9',4,'stroke-dasharray="36 24"');
 svg+=repeat(6,n=>L(n*138,53,n*138,284,'#687780',11))+L(0,55,800,55,'#637c85',15);
 svg+=repeat(7,n=>R(18+n*125,93,46,40,'#d0e6e1','opacity=".4"'));
}else if(family==='nature'){
 svg+=C(reverse?665:107,71,42,'#fbe4ae')+repeat(3,n=>G('translate('+((n*271+seed%100)%800)+' '+(45+n*42)+')',cloud(0,0,.65,'#f6efdc')));
 svg+=P('M0 302L139 165L251 287L414 128L575 297L695 206L800 294L800 460L0 460Z','#90b7a4');
 svg+=P('M0 355Q151 278 302 360T604 333T800 340L800 460L0 460Z','#699c87');
 svg+=P('M0 418Q143 350 287 422T580 396T800 411L800 460L0 460Z','#547f71');
 svg+=repeat(7,n=>G('translate('+((n*118+seed%53)%800)+' '+(294+(n%2)*29)+')',L(0,57,0,-18,'#7d7169',11)+C(0,-27,23+(n%3)*9,['#63907b','#75a087','#89ae8c'][n%3])));
}else if(family==='culture'){
 svg+=R(0,0,800,363,'#d3c1ad')+R(0,360,800,100,'#9b887c');
 svg+=repeat(6,n=>R(n*149,75,20,285,'#b4a08e')+R(n*149-6,75,32,16,'#e4cdb1'));
 svg+=R(55,115,185,220,'#927d72')+R(65,126,165,196,'#f0dcc1');
 svg+=R(288,102,222,239,'#8e7d7a')+R(299,115,201,216,'#e8dac3');
 svg+=R(560,118,182,222,'#977f7b')+R(572,130,158,200,'#f2dfc4');
 svg+=R(0,357,800,14,'#776b69')+repeat(9,n=>L(n*102,374,n*102+43,460,'#d0b29d',2));
}else if(family==='work'){
 svg+=R(0,0,800,360,'#bcc7c1')+R(0,361,800,99,'#81928f');
 svg+=repeat(9,n=>L(n*95,0,n*95-25,360,'#96a8a3',2,'opacity=".6"'))+R(0,66,800,18,'#75878d');
 svg+=R(20,120,205,182,'#637d82','rx="8"')+repeat(3,n=>R(31,147+n*49,183,11,'#b0bdab'));
 svg+=R(515,123,256,184,'#7a9293','rx="9"')+R(527,135,233,154,'#c6d0c0');
 svg+=R(0,327,800,27,'#7c817d')+repeat(4,n=>R(n*197+27,362,174,95,'#8e9c95'));
}else if(family==='leisure'){
 svg+=R(0,0,800,280,'#9db7bb')+R(0,277,800,183,'#bfaa9c');
 svg+=C(677,76,46,'#f4d9a7','opacity=".7"');
 svg+=P('M0 295L165 174L288 273L432 151L588 272L739 191L800 236L800 335L0 335Z','#789d9d');
 svg+=repeat(6,i=>R(15+i*155,291,30,55,'#e2c5a2')+P('M'+(i*155+1)+' 298L'+(i*155+30)+' 266L'+(i*155+62)+' 298Z','#c58c83'));
 svg+=R(0,370,800,17,'#e4cbae')+repeat(12,i=>L(i*70,379,i*70,460,'#a48f85',2));
}else if(family==='fantasy'){
 svg+=R(0,0,800,460,'#363f6c')+repeat(65,n=>star((n*79+seed)%800,(n*53+seed%27)%303,1+(n%3),'#e5dbed'));
 svg+=C(reverse?135:667,88,59,'#d7cded','opacity=".8"');
 svg+=P('M0 310L134 185L244 300L377 155L540 308L685 193L800 292L800 460L0 460Z','#66769e');
 svg+=P('M0 394Q134 327 278 390T570 364T800 380L800 460L0 460Z','#6c86a0');
 svg+=repeat(6,n=>G('translate('+((n*147+seed%91)%800)+' '+(358+n%2*29)+')',P('M-20 12L0 -56L20 12Z',['#9ac6b9','#a7aad9','#d5abbf'][n%3])+L(0,12,0,38,'#706e8a',6)));
}else{
 svg+=R(0,0,800,460,'#283b56')+repeat(53,i=>star((i*97+seed)%800,(i*43+27)%385,1+(i%3),'#bcdde4'));
 svg+=P('M0 391L800 360L800 460L0 460Z','#667a93')+R(0,342,800,24,'#8395a3');
 svg+=R(25,97,165,188,'#758ba0','rx="15"')+repeat(5,n=>R(40,115+n*32,133,22,'#2d5d78','rx="4"')+R(49+n*23,120+n*32,12,12,'#a3d5c8'));
 svg+=R(610,112,162,190,'#72869e','rx="11"')+repeat(4,n=>R(623,135+n*38,138,22,'#3a6076','rx="4"'));
 svg+=L(87,330,242,424,'#768a9e',12)+L(716,325,567,424,'#768a9e',12);
}
svg+=R(0,0,800,460,'url(#grain)');
return svg;
}
function spotColors(cfg){
return ['#f8e3b9',cfg.accent,'#608b85','#dab078','#ac91ad','#79bcc3','#c77d7c'];
}
