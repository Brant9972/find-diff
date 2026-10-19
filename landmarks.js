
const LAND={
 building:(color,roof='#a96e6b')=>R(18,30,167,105,color,'rx="6"')+P('M6 41L99 5L195 41Z',roof)+R(78,91,42,45,'#684d59')+R(28,61,33,27,COL.cream)+R(146,61,29,27,COL.cream),
 shelf:(color)=>R(13,17,174,122,color,'rx="6"')+[49,87,124].map(y=>R(22,y,157,5,'#63495b')).join('')+Array.from({length:24},(_,i)=>R(26+(i%8)*19,27+Math.floor(i/8)*38,11+(i%3),20+((i*7)%12),['#edb57c','#84bfac','#c48da1','#c4b9df'][i%4])).join(''),
 wheels:(c)=>C(55,129,19,'#354457')+C(149,129,19,'#354457')+C(55,129,8,c)+C(149,129,8,c),
 tree:()=>L(99,74,99,149,'#795d58',17)+C(70,63,41,'#598a72')+C(126,50,46,'#699d7b')+C(93,28,40,'#85b98b')
};
function drawLandmark(type,accent,alt){
 let s='',b=accent,w=COL.cream,k=COL.ink,g=COL.gold,p=COL.pink,m=COL.mint,wood=COL.wood,blu=COL.blue;
 switch(type){
 case 'florist':s+=LAND.building('#e8b4a4','#aa7788')+R(34,35,130,23,b)+T(99,52,'FLOWERS',16,k)+R(38,101,125,13,wood)+[48,79,110,142].map(x=>P('M'+(x-8)+' 104L'+(x+8)+' 104L'+(x+5)+' 91L'+(x-5)+' 91Z',p)+C(x,88,9,g)).join('');break;
 case 'record':s+=LAND.shelf('#453a59')+C(99,74,43,k)+C(99,74,32,b)+C(99,74,12,w)+C(99,74,4,k)+T(99,136,'VINYL',14,w);break;
 case 'lighthouse':s+=P('M81 138L104 18L132 138Z',w)+R(100,18,17,19,b)+P('M92 19L108 5L125 19Z',p)+L(85,90,128,90,wood,4)+R(104,111,12,26,k)+C(110,28,5,g);break;
 case 'tent':s+=P('M12 139L98 20L190 139Z',b)+P('M98 20L99 139L190 139Z','#db8b67')+P('M70 139L99 81L128 139Z',k)+L(100,22,100,8,wood,3)+P('M100 9L126 18L100 26Z',g);break;
 case 'ramen':s+=LAND.building('#b86d62','#694957')+R(29,40,141,25,k)+T(99,57,'ラーメン',17,g)+R(33,85,133,49,wood)+[52,83,114,145].map(x=>R(x,69,15,16,w)+C(x+7,75,3,p)).join('');break;
 case 'capsule':s+=R(22,20,155,122,'#8498c6','rx="20"')+R(41,37,118,69,k,'rx="13"')+R(48,45,100,54,'#315571','rx="9"')+C(102,70,24,blu)+L(25,116,174,116,m,5)+R(79,113,46,26,w);break;
 case 'train':s+=R(11,30,181,104,'#648b8e','rx="18"')+R(25,43,150,51,k,'rx="6"')+[39,84,129].map(x=>R(x,50,34,36,blu,'rx="3"')).join('')+R(25,100,150,25,b)+C(51,133,13,k)+C(153,133,13,k);break;
 case 'bookshop':s+=LAND.shelf('#947269')+R(61,91,78,47,'#c58e72')+T(99,112,'BOOKS',15,w)+[69,91,113].map(x=>R(x,119,16,15,blu)).join('');break;
 case 'busstop':s+=L(23,18,23,137,k,6)+L(175,18,175,137,k,6)+P('M12 22L95 2L190 22Z',b)+R(24,36,150,76,'#a6c8d8','opacity=".46"')+R(38,110,130,8,wood)+R(56,120,6,18,k)+R(139,120,6,18,k)+T(99,25,'BUS',13,k);break;
 case 'coral':s+=L(45,135,43,58,p,11)+L(43,89,20,69,p,8)+L(43,103,72,72,p,9)+L(140,139,142,47,m,11)+L(142,81,168,54,m,7)+L(142,91,117,69,m,8)+P('M0 139Q45 102 80 136T199 129L199 145L0 145Z','#d3c19c');break;
 case 'glasshouse':s+=P('M8 51L98 3L192 51L192 137L8 137Z','#b9e3dc','opacity=".72"')+[28,63,98,133,168].map(x=>L(x,49,x,137,'#6f9e90',2.5)).join('')+L(9,50,191,50,'#6f9e90',4)+[55,107,155].map(x=>C(x,117,18,m)+R(x-9,126,18,12,wood)).join('');break;
 case 'observatory':s+=LAND.building('#7d79a7','#434b78')+C(99,36,54,'#d5c8e7')+P('M41 46Q99 -45 158 46Z','#66699c')+R(83,63,32,46,k)+R(93,17,11,28,wood)+C(100,20,9,w);break;
 case 'candy':s+=R(22,21,155,116,'#dd9ca9','rx="10"')+R(38,32,122,65,'#ffedd5')+R(45,94,108,23,p)+P('M54 38L54 79L146 79L146 38',m)+[62,97,132].map(x=>C(x,56,13,b)).join('')+T(99,124,'SWEET',15,w);break;
 case 'easel':s+=L(45,136,97,5,wood,7)+L(155,136,103,5,wood,7)+R(56,18,90,92,w)+R(69,29,65,64,'#83bbcc')+C(107,45,13,g)+P('M72 90L94 61L112 84L124 68L134 91Z',m)+L(43,114,157,114,wood,7);break;
 case 'ski':s+=P('M0 130L93 18L199 131Z',w)+P('M95 20L96 132L199 131Z','#b4dbef')+L(29,129,165,129,b,3)+[57,143].map(x=>L(x,78,x+12,112,wood,4)+L(x+12,112,x+30,124,wood,2)).join('');break;
 case 'fishstall':s+=R(14,27,173,113,'#88b9bc')+P('M5 32L32 6L173 6L196 32Z',p)+R(30,93,146,17,wood)+[55,104,148].map(x=>E(x,100,22,10,blu)+P('M'+(x-20)+' 100L'+(x-35)+' 89L'+(x-35)+' 111Z',b)).join('')+T(100,53,'FRESH FISH',13,k);break;
 case 'catcafe':s+=LAND.building('#d5b293','#a77b72')+R(36,79,126,18,wood)+[50,94,137].map(x=>C(x,77,13,b)+P('M'+(x-10)+' 69L'+(x-9)+' 56L'+x+' 64Z',b)+P('M'+(x+10)+' 69L'+(x+9)+' 56L'+x+' 64Z',b)).join('')+T(100,53,'CAT CAFE',14,k);break;
 case 'dinosaur':s+=R(8,16,184,124,'#d5bfa6')+P('M28 96Q80 19 142 57Q183 50 170 110L145 110L130 90L90 114L40 114Z','#998c80')+C(149,63,3,k)+L(60,112,70,138,k,8)+L(116,104,125,138,k,8)+T(100,34,'FOSSILS',12,w);break;
 case 'spaceport':s+=R(10,53,179,88,'#869ac9')+P('M64 139L93 19L121 139Z','#eee7da')+P('M94 14L107 53L80 53Z',p)+C(94,76,12,blu)+P('M64 111L47 136L64 126Z',b)+P('M120 111L141 136L120 126Z',b)+L(19,45,180,45,w,3);break;
 case 'store':s+=LAND.building('#728ba3','#47566a')+R(29,39,144,26,b)+T(100,57,'24 HOURS',15,k)+R(36,80,135,52,'#a1d3d7')+[58,96,134].map(x=>R(x,94,18,24,g)+R(x+4,87,10,7,p)).join('');break;
 case 'stage':s+=R(6,5,187,135,'#5a3a53')+P('M8 6L62 6Q47 84 30 137L6 137Z','#bd7189')+P('M192 6L135 6Q151 84 168 137L194 137Z','#bd7189')+P('M45 113Q99 52 154 113L154 133L45 133Z',b)+C(100,68,29,g,'opacity=".28"')+T(100,38,'THEATRE',13,w);break;
 case 'rooftop':s+=R(24,58,152,84,'#7a9b96')+R(36,23,126,37,'#bbded1')+R(52,37,38,24,blu)+R(103,37,43,24,blu)+R(33,129,143,12,wood)+[49,90,132,161].map(x=>C(x,122,13,m)+R(x-7,132,14,8,wood)).join('');break;
 case 'oasis':s+=P('M0 125Q46 79 85 121T199 121L199 144L0 144Z','#d3b87a')+E(101,129,71,13,blu)+L(34,103,49,15,wood,10)+[10,28,48,66].map(x=>P('M49 20Q'+x+' -4 '+x+' 29Q39 29 49 20',m)).join('')+C(144,112,17,g);break;
 case 'aquarium':s+=R(7,13,186,128,'#4a718b','rx="7"')+R(17,26,166,104,'#65bad0','rx="4"')+[56,121,155].map((x,i)=>E(x,70+i*13,19,9,i%2?p:g)+P('M'+(x-18)+' '+(70+i*13)+'L'+(x-28)+' '+(59+i*13)+'L'+(x-28)+' '+(81+i*13)+'Z',m)).join('')+P('M25 127Q51 82 75 122T173 123L173 130L25 130Z',m);break;
 case 'potion':s+=LAND.shelf('#55425a')+[52,99,151].map((x,i)=>R(x-13,68,26,35,[p,m,b][i],'rx="9"')+R(x-5,60,10,8,w)+C(x,85,6,g)).join('')+T(101,35,'SPELLS',14,w);break;
 case 'airport':s+=R(12,28,176,111,'#739db6')+R(28,40,143,57,'#c3d9df')+P('M36 76L163 49L122 84Z',w)+L(18,108,180,108,k,3)+[53,95,135].map(x=>R(x,115,23,19,k)).join('')+T(100,20,'DEPARTURES',13,w);break;
 case 'clockshop':s+=LAND.shelf('#73565b')+[54,103,151].map((x,i)=>C(x,66,25,[w,g,b][i])+C(x,66,20,k)+L(x,66,x,51,w,2)+L(x,66,x+11,73,w,2)).join('');break;
 case 'wheel':s+=C(100,64,59,'none','stroke="'+w+'" stroke-width="5"')+[0,1,2,3,4,5,6,7].map(i=>{let a=i*Math.PI/4;return L(100,64,100+59*Math.cos(a),64+59*Math.sin(a),w,2.7)+C(100+59*Math.cos(a),64+59*Math.sin(a),8,[p,g,b][i%3]);}).join('')+L(100,64,56,139,k,6)+L(100,64,144,139,k,6);break;
 case 'waterfall':s+=P('M0 139L46 45L80 91L128 19L199 138Z','#477d70')+P('M104 28Q89 68 111 98Q116 124 95 139L148 139Q119 114 135 94Q114 60 128 20Z',blu)+E(122,135,71,10,'#94d4d3')+[38,174].map(x=>C(x,124,28,m)).join('');break;
 case 'onsen':s+=LAND.building('#cfab9f','#7a798e')+P('M33 99Q99 56 167 99L167 139L33 139Z',blu)+[52,100,147].map(x=>P('M'+x+' 82Q'+(x-10)+' 67 '+x+' 50','none','stroke="'+w+'" stroke-width="4"')).join('')+T(100,43,'♨',23,p);break;
 case 'camera':s+=R(11,29,175,106,k,'rx="15"')+R(69,15,65,24,b)+C(99,83,49,'#5f7486')+C(99,83,33,w)+C(99,83,23,'#597aa5')+C(99,83,11,k)+R(153,46,18,13,p);break;
 case 'castlemarket':s+=LAND.building('#cdb18a','#8f7580')+R(30,60,140,39,p)+[40,78,116,154].map(x=>P('M'+x+' 62L'+(x+14)+' 62L'+(x+7)+' 77Z',g)).join('')+R(36,102,128,33,wood)+T(99,51,'MARKET',14,k);break;
 case 'pirateship':s+=P('M4 106L195 106L173 141L30 141Z',wood)+L(97,10,97,110,k,6)+P('M92 23L92 97L31 97Z',w)+P('M104 20L104 93L161 93Z',p)+P('M99 12L126 18L99 29Z',k)+[42,87,134].map(x=>C(x,118,4,g)).join('');break;
 case 'wintertown':s+=LAND.building('#dce7ef','#8095ac')+P('M4 43L99 5L195 43Z',w)+R(75,93,46,47,'#9bafc0')+[43,149].map(x=>R(x,69,23,23,g)).join('')+C(98,6,12,w);break;
 case 'arcade':s+=R(24,5,150,132,'#4d4b80','rx="9"')+[42,106].map((x,i)=>R(x,22,52,88,['#615b92','#527c92'][i],'rx="7"')+R(x+6,35,40,40,k)+C(x+20,95,6,p)+C(x+36,95,5,g)).join('')+T(99,18,'ARCADE',13,w);break;
 case 'beach':s+=P('M0 140Q82 80 199 131L199 140Z','#ecc8a0')+L(99,39,99,138,wood,5)+P('M9 48Q80 -12 99 40Q165 -12 193 48Z',p)+L(99,40,99,138,w,1.5)+R(36,104,82,7,b)+L(52,110,38,136,k,3)+C(170,25,19,g);break;
 case 'picnic':s+=LAND.tree()+P('M33 132L161 132L181 143L20 143Z',p)+R(43,118,113,15,w)+[70,99,131].map(x=>C(x,110,12,g)).join('');break;
 case 'workshop':s+=R(9,16,180,124,'#64869a')+R(21,31,152,52,k)+[42,78,114,150].map(x=>C(x,54,14,blu)+C(x,54,7,g)).join('')+R(39,99,122,27,wood)+C(54,124,16,k)+C(152,124,16,k);break;
 case 'vineyard':s+=P('M0 139Q80 30 199 139Z','#8bad88')+[37,82,126,170].map(x=>L(x,61,x,137,wood,4)+[82,104,124].map(y=>C(x,y,11,p)).join('')).join('')+P('M80 128L112 128L107 139L86 139Z',wood);break;
 case 'submarine':s+=E(101,83,92,47,g)+E(99,83,78,37,'#dfac70')+[59,99,139].map(x=>C(x,85,18,k)+C(x,85,13,blu)).join('')+R(88,23,27,23,g)+P('M9 80L0 42L0 120Z',wood);break;
 case 'library':s+=LAND.shelf('#93796a')+R(62,104,80,35,wood)+R(66,106,73,11,w)+T(100,119,'READ',10,k);break;
 case 'shelter':s+=LAND.building('#b8cab1','#85ab9b')+P('M40 123L99 65L160 123Z',wood)+R(71,113,56,25,k)+C(101,119,9,b)+T(100,51,'ADOPT',13,k);break;
 case 'supermarket':s+=LAND.shelf('#89ad99')+R(13,26,174,25,g)+T(99,43,'FRESH',16,k)+[44,81,120,155].map((x,i)=>C(x,99,14,[p,g,m,b][i])).join('');break;
 case 'moonbase':s+=P('M19 130L32 76L74 32L131 32L177 76L188 130Z','#c1cadf')+R(51,74,99,55,'#6989ad')+R(71,47,59,38,w)+C(100,66,20,blu)+C(100,66,9,k)+[43,160].map(x=>C(x,123,13,w)).join('');break;
 case 'wedding':s+=P('M24 139Q35 3 100 8Q165 3 176 139','none','stroke="'+w+'" stroke-width="14"')+P('M58 132Q99 83 141 132L141 139L58 139Z',p)+[36,62,88,115,141,166].map(x=>C(x,58+(x%4)*12,7,g)).join('')+T(100,105,'♡',28,w);break;
 case 'temple':s+=P('M13 139L29 54L98 9L171 54L187 139Z','#b7a176')+R(35,62,130,72,'#8a815f')+[52,89,127].map(x=>R(x,67,19,66,g)+R(x-4,65,27,10,wood)).join('')+P('M78 133L100 98L123 133Z',k);break;
 case 'treehouse':s+=LAND.tree()+R(41,62,122,65,wood)+P('M28 66L100 20L177 66Z',b)+R(80,91,36,36,k)+[52,147].map(x=>R(x-12,77,24,22,w)).join('')+L(146,122,170,141,wood,5);break;
 case 'laundry':s+=R(13,13,174,125,'#7c9dae')+[36,102].map(x=>R(x,37,60,84,w,'rx="5"')+C(x+30,79,23,k)+C(x+30,79,18,blu)+E(x+30,84,17,9,m)).join('')+T(99,29,'LAUNDRY',13,k);break;
 case 'neoncity':s+=R(14,13,48,128,k)+R(70,28,53,112,'#52627e')+R(132,2,55,138,'#373a5b')+[39,95,160].map((x,i)=>R(x-13,38,26,49,[p,m,g][i])+T(x,67,['夜','光','街'][i],24,k)).join('');break;
 case 'canal':s+=P('M0 90L48 60L80 60L120 40L170 55L199 92L199 140L0 140Z','#d9b8a2')+P('M0 104Q99 69 199 105','none','stroke="'+wood+'" stroke-width="15"')+P('M3 136Q99 92 197 137Z',blu)+P('M54 133L137 133L118 143L67 143Z',wood)+L(98,96,98,132,k,3)+P('M98 98L128 130L98 130Z',w);break;
 }
 // Every scene has a unique structural focal point, not a generic repeated grid.
 let dx=alt?13:-9,dy=alt?4:0;
 return '<g transform="translate('+(139+dx)+' '+(65+dy)+')">'+s+'</g>';
}
