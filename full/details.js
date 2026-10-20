
// Authored micro-illustration vocabulary. The same visible prop may or may not be changed.
// Changed variants alter geometry, markings, counts and directions, not only fill colours.
function detailArt(type,variant,color,changed=false,caption=''){
const fg=color,ink='#465969',cream='#fff2d9',mint='#8fc6b1',gold='#e6c386',pink='#dc9e9f',blue='#85bec9';
let s='';
switch(type){
case 'sign':
  s+=R(-40,-18,80,37,'#416776','rx="6" stroke="#e8d8b8" stroke-width="3"')+T(0,0,caption||'OPEN',13,cream)+R(31,7,5,5,changed?pink:gold);break;
case 'plaque':
  s+=R(-28,-23,56,47,'#c6b293','rx="4"')+R(-23,-18,46,37,'#eed9b6')+T(0,-5,changed?'8':'6',18,ink)+L(-16,9,changed?2:16,9,ink,2);break;
case 'leaf':
  s+=L(0,23,0,-26,ink,3)+P('M0 -20Q-35 -37 -25 -8Q-11 -9 0 -20',mint)+P('M0 -14Q33 -32 26 -1Q11 -3 0 -14',fg)+P(changed?'M0 7Q-27 1 -22 20Q-7 21 0 7':'M0 7Q-18 2 -15 15Q-7 18 0 7',mint);break;
case 'flower':
  s+=L(0,12,0,30,ink,3)+repeat(changed?4:5,i=>{let a=i*Math.PI*2/(changed?4:5);return C(Math.cos(a)*14,Math.sin(a)*14,9,fg)})+C(0,0,8,gold);break;
case 'bird':
  s+=E(0,8,24,15,fg)+C(15,-5,13,fg)+P('M26 -5L40 0L26 7Z',gold)+C(20,-8,2,ink)+P('M-19 7L-35 -15L-34 20Z',fg)+P(changed?'M-8 8Q-28 -17 -4 -22':'M-8 8Q-2 -21 12 -14','none','stroke="'+cream+'" stroke-width="5"');break;
case 'cloud':
  s+=C(-12,6,17,cream)+C(4,-6,22,cream)+C(21,7,17,cream)+R(-30,7,63,12,cream)+C(changed?-6:23,6,5,blue);break;
case 'window':
  s+=R(-29,-27,58,54,cream,'rx="3" stroke="'+ink+'" stroke-width="4"')+R(-24,-22,48,44,blue)+L(0,-22,0,22,cream,3)+L(-24,changed?4:0,24,changed?4:0,cream,4);break;
case 'clock':
  s+=C(0,0,28,cream)+C(0,0,24,'#a9c8c2')+C(0,0,3,ink)+L(0,0,0,-17,ink,3)+L(0,0,changed?19:12,changed?-2:14,ink,3);break;
case 'flag':
  s+=L(-22,-30,-22,29,ink,4)+P('M-20 -29L35 -18L24 2L-20 -6Z',fg)+P(changed?'M-20 -6L4 0L-20 13Z':'M-20 -6L-1 -2L-20 8Z',gold);break;
case 'bottle':
  s+=R(-9,-29,18,9,cream)+R(-17,-19,34,47,fg,'rx="8"')+R(-13,-4,26,22,cream,'rx="4"')+T(0,8,changed?'✦':'●',16,ink);break;
case 'poster':
  s+=R(-29,-29,58,58,ink,'rx="4"')+R(-24,-24,48,48,fg)+C(7,-10,9,gold)+P('M-22 18L-3 -8L9 5L18 -3L24 20Z',mint)+P(changed?'M-20 -10L-4 -18L2 -7Z':'M-20 -10L-4 -18L-4 -7Z',cream);break;
case 'book':
  s+=R(-22,-26,45,53,fg,'rx="3"')+R(-15,-26,5,53,ink)+R(-5,-14,21,4,cream)+R(-5,-4,changed?13:21,4,cream)+R(-5,8,20,3,cream);break;
case 'ticket':
  s+=R(-30,-18,60,35,cream,'rx="5"')+R(-22,-13,43,25,fg,'rx="2"')+T(0,2,changed?'27':'21',17,ink)+L(23,-17,23,17,cream,1.8,'stroke-dasharray="3 3"');break;
case 'gear':
  s+=C(0,0,24,ink)+C(0,0,18,fg)+C(0,0,7,cream)+repeat(changed?7:8,i=>{let a=i*Math.PI*2/(changed?7:8);return R(Math.cos(a)*23-5,Math.sin(a)*23-4,10,8,fg)});break;
case 'lantern':
  s+=L(0,-28,0,-19,ink,3)+E(0,0,20,25,fg)+L(-20,0,20,0,cream,2)+C(0,0,7,gold)+L(0,24,0,changed?30:39,ink,2.5);break;
case 'glass':
  s+=P('M-15 -23L14 -23L10 20Q0 30 -10 20Z',blue)+E(0,-23,15,5,cream)+P('M-12 -4L12 -4L10 19L-9 19Z',changed?fg:gold)+L(0,27,0,35,ink,2);break;
case 'cup':
  s+=P('M-22 -8L19 -8L15 21L-15 21Z',fg)+P('M17 -5Q39 -14 32 12L17 14','none','stroke="'+fg+'" stroke-width="6"')+E(-2,-8,21,7,cream)+P(changed?'M-9 -17Q-21 -24 -6 -36':'M-9 -17Q-17 -30 -9 -40','none','stroke="'+cream+'" stroke-width="4"');break;
case 'fish':
  s+=E(0,0,29,15,fg)+P('M-23 0L-43 -16L-43 16Z',mint)+C(14,-6,3,ink)+P(changed?'M-6 -12L3 -29L13 -10Z':'M-6 -12L3 -23L13 -10Z',gold);break;
case 'shell':
  s+=P('M-29 20Q-28 -30 0 -27Q28 -30 29 20Z',fg)+L(0,-25,0,23,cream,2)+L(-20,-9,-10,22,cream,2)+(changed?L(18,-9,18,22,cream,2):L(17,-9,10,22,cream,2));break;
case 'basket':
  s+=P('M-27 -5L27 -5L21 29L-20 29Z',fg)+P('M-18 -7Q-19 -28 0 -28Q19 -28 19 -7','none','stroke="'+ink+'" stroke-width="5"')+repeat(changed?3:4,i=>L(-19+i*13,-2,-15+i*11,27,cream,2));break;
case 'crate':
  s+=R(-27,-23,54,47,fg,'rx="3"')+P('M-27 -23L27 24','none','stroke="'+cream+'" stroke-width="4"')+P('M27 -23L-27 24','none','stroke="'+cream+'" stroke-width="4"')+R(changed?-17:12,-14,6,7,ink);break;
case 'battery':
  s+=R(-24,-24,48,48,ink,'rx="6"')+R(-19,-19,38,38,fg,'rx="4"')+R(-8,-29,16,5,cream)+repeat(changed?3:4,i=>R(-13+i*7,2,5,12,cream));break;
case 'planet':
  s+=C(0,0,23,fg)+E(0,0,40,11,'none','stroke="'+cream+'" stroke-width="4" transform="rotate(-23)"')+C(changed?-8:11,-8,5,mint)+C(9,12,3,gold);break;
case 'flowerpot':
  s+=P('M-22 11L22 11L16 29L-16 29Z','#a47b6b')+L(0,12,0,-25,ink,3)+E(-13,-8,10,6,mint,'transform="rotate(22 -13 -8)"')+E(14,-16,10,6,mint,'transform="rotate(-23 14 -16)"')+(changed?E(-11,2,7,4,mint):E(9,-3,8,4,mint));break;
case 'candy':
  s+=C(0,0,17,fg)+P('M-15 -10L-34 -20L-32 0L-15 10Z',gold)+P('M15 -10L34 -20L32 0L15 10Z',gold)+repeat(changed?2:3,i=>L(-8+i*8,-9,-8+i*8,10,cream,2));break;
case 'fruit':
  s+=E(0,3,22,24,fg)+L(0,-19,4,-32,ink,3)+E(12,-25,12,5,mint,'transform="rotate(-18 12 -25)"')+C(changed?-7:8,2,4,cream);break;
case 'ribbon':
  s+=C(0,0,8,gold)+P('M-6 -3Q-35 -30 -33 2Q-31 18 -6 3Z',fg)+P('M6 -3Q35 -30 33 2Q31 18 6 3Z',fg)+P('M-3 4L-14 31L0 27L6 7Z',fg)+(changed?P('M5 5L18 29L23 23Z',fg):P('M5 5L13 29L24 23Z',fg));break;
case 'chair':
  s+=R(-19,-26,38,39,fg,'rx="6"')+R(-25,12,50,8,ink)+L(-17,20,-17,35,ink,4)+L(17,20,17,35,ink,4)+L(-16,changed?-12:-17,16,changed?-12:-17,cream,3);break;
case 'lamp':
  s+=L(0,-28,0,-17,ink,3)+P('M-24 3L-15 -18L15 -18L24 3Z',fg)+C(0,5,9,gold)+L(-20,5,20,5,cream,3)+L(0,7,0,changed?21:14,cream,2);break;
case 'radio':
  s+=R(-27,-17,54,43,fg,'rx="6"')+R(-19,-9,31,24,'#446479')+C(19,4,8,cream)+L(-16,-16,changed?14:5,-39,ink,3);break;
case 'star':
  s+=star(0,0,changed?10:15,fg)+C(23,20,5,gold);break;
case 'note':
  s+=R(-25,-31,50,62,cream)+repeat(changed?4:5,i=>L(-16,-17+i*10,16,-17+i*10,ink,2))+C(17,21,4,fg);break;
case 'stripe':
  s+=R(-27,-25,54,50,fg)+repeat(changed?3:4,i=>R(-24+i*13,-21,9,42,cream));break;
case 'tile':
  s+=R(-27,-26,54,52,cream,'stroke="'+ink+'" stroke-width="3"')+P(changed?'M-20 16L0 -12L20 17Z':'M-20 17L0 -17L20 17Z',fg)+C(0,9,6,gold);break;
case 'clockface':
  s+=C(0,0,28,fg)+C(0,0,22,cream)+L(0,0,0,-17,ink,3)+L(0,0,changed?17:-16,changed?6:5,ink,3)+C(0,0,3,ink);break;
case 'wing':
  s+=P('M-30 11L29 -25L20 9L-8 27Z',fg)+L(-13,12,15,1,cream,3)+(changed?L(15,1,29,2,cream,3):L(15,1,23,-8,cream,3));break;
case 'lock':
  s+=R(-20,-1,40,33,fg,'rx="5"')+P('M-12 2L-12 -11Q-12 -27 0 -27Q12 -27 12 -11L12 2','none','stroke="'+ink+'" stroke-width="5"')+C(0,13,5,cream)+L(0,15,changed?0:4,25,cream,2);break;
case 'compass':
  s+=C(0,0,28,fg)+C(0,0,22,cream)+P(changed?'M0 -17L8 0L0 16L-3 0Z':'M0 -17L6 0L0 16L-6 0Z',ink)+C(0,0,3,gold);break;
case 'snow':
  s+=repeat(6,i=>{let a=i*Math.PI/3;return L(0,0,Math.cos(a)*28,Math.sin(a)*28,cream,3)})+C(0,0,changed?7:3,fg);break;
default:
  s+=R(-26,-25,52,50,fg,'rx="9"')+C(0,0,15,cream)+T(0,1,changed?'✦':'★',17,ink);
}
return '<g>'+s+'</g>';
}
function detailG(type,variant,color,changed,x,y,k=1,rotation=0,caption=''){
return G('translate('+x+' '+y+') rotate('+rotation+') scale('+k+')',detailArt(type,variant,color,changed,caption));
}
const DETAIL_TYPES=['sign','plaque','leaf','flower','bird','cloud','window','clock','flag','bottle','poster','book','ticket','gear','lantern','glass','cup','fish','shell','basket','crate','battery','planet','flowerpot','candy','fruit','ribbon','chair','lamp','radio','star','note','stripe','tile','clockface','wing','lock','compass','snow'];
