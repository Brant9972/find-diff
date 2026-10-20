
/* Standalone landmark illustrations normalized around a 240×175 focal frame. */
const HERO={};
function heroShelf(c){return R(4,18,220,137,c,'rx="8"')+repeat(3,n=>R(12,51+n*40,205,7,'#735b64'))}
function heroBuilding(c){return R(22,10,192,151,c,'rx="6"')+P('M0 24L119 -20L236 24Z','#9d7b75')+R(94,112,44,49,'#725c62')+R(45,45,40,39,'#c6dcd1')+R(157,45,35,39,'#c6dcd1')}
function heroCart(c){return R(23,76,189,64,c,'rx="7"')+R(40,130,23,24,'#665760')+R(175,130,23,24,'#665760')+C(53,157,22,'#555663')+C(186,157,22,'#555663')+C(53,157,10,'#dad4b9')+C(186,157,10,'#dad4b9')}
function heroCanopy(c){return P('M1 48L237 48L209 103L26 103Z',c)+repeat(7,i=>P('M'+(1+i*34)+' 48L'+(35+i*34)+' 48L'+(30+i*34)+' 103L'+(19+i*31)+' 103Z',i%2?'#f5d9b4':c))}
function heroPlant(c){return L(122,145,122,16,'#766b68',17)+repeat(5,i=>C(65+i*26,38+(i%2)*18,36,c))+C(122,12,39,c)}
function heroShine(x,y,c){return star(x,y,5,c)+star(x+39,y-15,3,c)+star(x-27,y+19,2.5,c)}
const H1={
auction:(c)=>heroCanopy(c)+heroCart('#b88b74')+repeat(5,i=>G('translate('+(41+i*39)+' 55)',plant(0,0,.43)))+R(62,24,122,22,'#527b75')+T(121,35,'花卉交易',15,'#fff0cb'),
chinatown:(c)=>heroBuilding('#bf8881')+P('M-18 24L120 -44L257 24Z',c)+repeat(4,i=>R(i*42+40,34,18,101,'#926265'))+repeat(4,i=>G('translate('+(46+i*49)+' 21)',E(0,13,12,17,'#edc692')+L(0,-12,0,-1,'#ad816f',3))),
barber:(c)=>heroBuilding('#c0aa9d')+R(119,22,21,135,'#f6e3cf')+repeat(6,i=>P('M119 '+(24+i*22)+'L140 '+(37+i*22)+'L140 '+(48+i*22)+'L119 '+(35+i*22)+'Z',i%2?'#bb7785':'#6198a3')+T(119,7,'BARBER',24,'#f8e6d2'),
timewindow:(c)=>heroBuilding('#9e8b84')+C(121,68,73,'#e5cb9b')+C(121,68,59,'#fff1d5')+repeat(12,i=>{let a=i*Math.PI/6;return L(121+Math.cos(a)*48,68+Math.sin(a)*48,121+Math.cos(a)*54,68+Math.sin(a)*54,'#6b6565',3)})+L(121,68,121,26,'#645e64',5)+L(121,68,155,79,'#645e64',4),
postoffice:(c)=>heroBuilding('#cd9b81')+R(34,32,170,28,'#64798a')+T(118,47,'POST',22,'#f9e7d2')+R(139,99,52,74,'#b86e67','rx="8"')+R(149,107,31,7,'#ecd4bd')+P('M156 138L180 138L172 155L163 155Z','#f0d5ad'),
bicycle:(c)=>heroBuilding('#9db9b7')+C(63,115,44,'none','stroke="#48616a" stroke-width="7"')+C(176,115,44,'none','stroke="#48616a" stroke-width="7"')+L(63,115,119,67,'#a77e6c',7)+L(119,67,176,115,'#a77e6c',7)+L(63,115,140,115,'#a77e6c',7)+L(140,115,119,67,'#a77e6c',7)+L(115,65,144,65,'#425b64',5),
shoemaker:(c)=>heroBuilding('#d5b7a2')+P('M46 99L107 86L125 120L201 124L198 153L36 153Z','#775c5b')+P('M45 111L108 99L128 131L201 131','none','stroke="#f1cdac" stroke-width="6"')+C(76,116,5,'#dfc194')+C(89,115,5,'#dfc194'),
lantern:(c)=>heroBuilding('#bc7d80')+repeat(5,i=>G('translate('+(34+i*40)+' 27)',E(0,36,16,26,['#ebb18b','#d8828c','#f1cb9d'][i%3])+L(-17,34,17,34,'#f9dfb8',4)+L(0,-8,0,9,'#f3dbad',3)+L(0,62,0,79,'#f3dbad',3))),
mural:(c)=>heroBuilding('#b2aba4')+P('M26 65L97 17L182 68L118 137Z','#81b8bf')+P('M30 88L101 45L196 110L72 160Z','#e8b48e')+C(128,81,30,c)+repeat(6,i=>L(35+i*31,131,51+i*31,144,'#7e819d',5)),
clocktower:(c)=>R(77,-37,86,207,'#b6a59a')+P('M62 -31L121 -77L180 -31Z','#788d96')+C(121,17,38,'#f5e9d0')+C(121,17,31,'#587486')+L(121,17,121,-9,'#fff1cf',4)+L(121,17,145,21,'#fff1cf',4)+R(97,97,45,76,'#7c6e71')+repeat(3,i=>R(89+i*22,67,13,20,'#e9cb99')),
breakfast:(c)=>heroCanopy('#e6ae85')+heroCart('#c6a17d')+repeat(3,i=>G('translate('+(60+i*58)+' 52)',E(0,0,28,13,'#f2dfbe')+E(0,-7,24,9,'#bb8f7d')+P('M-13 -9Q-26 -29 -8 -39','none','stroke="#fff1db" stroke-width="4"')))+T(120,115,'早餐',27,'#5b6266'),
donutshop:(c)=>heroBuilding('#edc1c0')+repeat(4,i=>G('translate('+(62+i%2*110)+' '+(51+Math.floor(i/2)*71)+')',C(0,0,29,'#c58d72')+C(0,0,19,['#f4adbd','#e6be86','#9ac9c9'][i%3])+C(0,0,8,'#5f646c')+repeat(5,j=>C(Math.cos(j*1.2)*14,Math.sin(j*1.2)*14,2,'#fff4cc')))),
bistro:(c)=>heroBuilding('#ad898f')+heroCanopy('#c27d7e')+R(50,118,142,9,'#ebcfad')+L(70,127,70,166,'#77676c',7)+L(172,127,172,166,'#77676c',7)+R(43,125,30,41,'#8a6f79')+R(176,125,30,41,'#8a6f79')+E(120,111,55,12,'#fff0d7'),
sushi:(c)=>heroCart('#89b2bb')+repeat(4,i=>G('translate('+(58+i*40)+' 94)',E(0,0,19,10,'#fff3df')+E(0,-6,16,7,['#e8a186','#a9c9b6','#d7b878'][i%3])+R(-8,-5,16,4,'#536c74')))+R(25,80,186,9,'#4b6674'),
teahouse:(c)=>heroBuilding('#96b39d')+E(120,110,77,32,c)+R(63,91,114,28,c,'rx="12"')+C(120,72,30,c)+C(120,67,13,'#f8e9c7')+P('M177 94Q232 62 214 116','none','stroke="#6d8c81" stroke-width="13"')+L(72,99,40,77,'#6d8c81',11),
pizza:(c)=>R(32,28,175,145,'#c38d72','rx="35"')+R(48,43,143,109,'#765963','rx="47"')+E(120,118,78,31,'#f2c18b')+C(120,105,53,'#e7a978')+repeat(7,i=>C(120+Math.cos(i)*35,105+Math.sin(i)*19,8,'#b96367'))+repeat(5,i=>C(120+Math.cos(i*2)*25,105+Math.sin(i*2)*12,4,'#79a38b')),
fruits:(c)=>heroCanopy('#ddac87')+heroCart('#b59b7d')+repeat(7,i=>C(46+i%4*42,110-Math.floor(i/4)*25,20,['#de846f','#f0c77d','#9cbf86'][i%3]))+repeat(3,i=>leaf(42+i*50,70,.7)),
icecreamvan:(c)=>heroCart('#b5d5d2')+R(19,34,189,49,'#94bfcb')+R(68,46,70,37,'#d6ecdc')+P('M180 93L202 93L191 128Z','#cf907e')+C(191,87,18,'#f2d5a0')+C(193,65,15,'#f2adb0')+T(118,66,'ICE CREAM',15,'#496e79'),
spices:(c)=>heroShelf('#a98580')+repeat(9,i=>G('translate('+(31+i%5*41)+' '+(30+Math.floor(i/5)*80)+')',R(-11,0,22,44,['#edc180','#a6bd96','#b87672','#d8b0a5'][i%4],'rx="5"')+R(-7,-7,14,9,'#f6e2be'))),
dessert:(c)=>heroShelf('#d9b0aa')+repeat(3,i=>G('translate('+(64+i*62)+' 112)',R(-27,1,54,35,['#e8a3af','#e3b3ca','#ddbd90'][i])+E(0,0,32,13,'#fff0e0')+C(0,-20,11,'#f4d1a7')+C(0,-30,5,'#e27f78')))+T(114,36,'CAKES',22,'#fff4ce'),
foresttrain:(c)=>heroCart('#659b8e')+R(21,24,179,65,'#a8c9b6')+repeat(4,i=>R(29+i*43,38,33,35,'#5f8595','rx="4"'))+R(160,81,42,52,'#d5b690'),
tram:(c)=>heroCart('#b97679')+R(21,12,191,74,'#dc9a91','rx="19"')+repeat(4,i=>R(34+i*43,29,33,41,'#a0cad1','rx="5"'))+L(121,12,121,-35,'#5c7378',5)+L(81,-36,158,-36,'#5c7378',5),
baggage:(c)=>heroCart('#799da9')+repeat(5,i=>G('translate('+(43+i*42)+' '+(73+i%2*8)+')',R(-14,-25,30,41,['#bd9aaa','#89aeca','#d5aa7b'][i%3],'rx="5"')+R(-7,-32,16,9,'#e9e1ce','rx="4"')))+R(26,114,186,13,'#526c79'),
ferry:(c)=>P('M8 103L228 103L202 161L39 161Z','#8a7c7d')+R(69,31,131,74,'#e9ddc4')+R(99,2,83,31,'#98b7b5')+repeat(5,i=>R(79+i*23,46,16,31,'#6da6af'))+C(56,121,17,'#f4e0c4')+C(56,121,10,'#d88d7e'),
taxi:(c)=>heroCart('#e7bf76')+R(41,51,154,36,'#efd390')+R(76,38,83,21,'#f7e0ac')+T(118,50,'TAXI',19,'#776665')+repeat(3,i=>R(62+i*49,91,33,22,'#adc5bd')),
gasstation:(c)=>R(19,26,201,44,c)+L(34,70,34,166,'#6c777d',12)+L(204,70,204,166,'#6c777d',12)+R(91,78,87,85,'#b8a5a2','rx="9"')+R(106,92,60,43,'#e8e8d3')+T(134,113,'95',29,'#bc8873')+P('M179 93Q219 94 203 131','none','stroke="#677983" stroke-width="8"'),
airhangar:(c)=>P('M0 49L119 -6L237 49L237 160L0 160Z','#95b2be')+R(17,63,203,97,'#516e80')+P('M11 89L222 91L222 111L11 111Z','#d4e5e1')+P('M116 87L187 126L116 120L53 145Z','#f4e9d9')+P('M111 85L105 32L130 32L134 85Z','#dad4c7'),
containers:(c)=>repeat(4,i=>R((i%2)*109+10,20+Math.floor(i/2)*69,103,63,['#ba817f','#819ba1','#d0a57a','#8bada6'][i])+repeat(5,k=>L((i%2)*109+25+k*16,23+Math.floor(i/2)*69,(i%2)*109+25+k*16,78+Math.floor(i/2)*69,'#f2e3d2',2,'opacity=".35"'))+L(212,-49,212,166,'#586d7f',8)+L(169,-43,235,-43,'#586d7f',8),
cablecar:(c)=>L(-15,-39,255,-39,'#566d78',7)+L(119,-39,119,20,'#7d9195',5)+R(58,26,126,104,'#a9ced0','rx="28" stroke="#587984" stroke-width="9"')+repeat(3,i=>R(67+i*37,42,32,54,'#78abb5'))+L(84,133,84,172,'#667c80',4)+L(160,133,160,172,'#667c80',4),
motorcycle:(c)=>C(53,136,36,'none','stroke="#4e5b67" stroke-width="10"')+C(193,136,36,'none','stroke="#4e5b67" stroke-width="10"')+P('M49 134L101 75L151 122L191 132L142 133Z',c)+L(101,74,125,62,'#6d6b75',7)+L(171,100,205,78,'#6d6b75',7)+R(91,69,48,11,'#a28e87')
};
Object.assign(HERO,H1);
