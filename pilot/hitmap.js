/* Precision hit masks derived from the actual SVG difference pixels, not guessed object centres. */
const HITMAP=(()=>{
  const W=800,H=460,CELL=4,GW=W/CELL,GH=H/CELL;
  function raster(markup){
    const svg='<svg xmlns="http://www.w3.org/2000/svg" width="800" height="460" viewBox="0 0 800 460">'+defs+markup+'</svg>';
    return new Promise((resolve,reject)=>{
      const im=new Image();
      im.onload=()=>{
        try{
          const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;
          const ctx=canvas.getContext('2d',{willReadFrequently:true});
          if(!ctx)throw new Error('Canvas unavailable');
          ctx.drawImage(im,0,0,W,H);
          resolve(ctx.getImageData(0,0,W,H).data);
        }catch(err){reject(err)}
      };
      im.onerror=()=>reject(new Error('SVG image failed to load'));
      im.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
    });
  }
  function build(a,b){
    const mask=new Uint8Array(GW*GH);
    let count=0,xsum=0,ysum=0,minx=W,miny=H,maxx=0,maxy=0;
    for(let y=0;y<H;y++)for(let x=0;x<W;x++){
      const i=(y*W+x)*4;
      const dr=Math.abs(a[i]-b[i]),dg=Math.abs(a[i+1]-b[i+1]),db=Math.abs(a[i+2]-b[i+2]),da=Math.abs(a[i+3]-b[i+3]);
      // Only substantial visual differences count; ignore antialias noise.
      const v=dr+dg+db+da*1.35;
      if(v<70)continue;
      mask[(y>>2)*GW+(x>>2)]=1;
      xsum+=x;ysum+=y;count++;
      if(x<minx)minx=x;if(x>maxx)maxx=x;
      if(y<miny)miny=y;if(y>maxy)maxy=y;
    }
    if(count<3)throw new Error('Spot contains no measurable image difference');
    const tx=xsum/count,ty=ysum/count;
    // The marker's centre must lie on a genuinely changed pixel, not in blank space.
    let centre={x:tx,y:ty},best=Infinity;
    for(let iy=Math.max(0,miny>>2);iy<=Math.min(GH-1,maxy>>2);iy++)
      for(let ix=Math.max(0,minx>>2);ix<=Math.min(GW-1,maxx>>2);ix++){
        if(!mask[iy*GW+ix])continue;
        let cx=ix*CELL+CELL/2,cy=iy*CELL+CELL/2,dist=(cx-tx)**2+(cy-ty)**2;
        if(dist<best){best=dist;centre={x:cx,y:cy}}
      }
    const span=Math.max(maxx-minx+1,maxy-miny+1);
    return {mask,centre,count,bounds:{x:minx,y:miny,w:maxx-minx+1,h:maxy-miny+1},ringWidth:Math.max(45,Math.min(100,span+26))};
  }
  async function one(spot){
    // Compare JUST this one authored overlay so other four clues cannot contaminate its hit area.
    const a=spot[3](false),b=spot[3](true);
    const images=await Promise.all([raster(a),raster(b)]);
    return build(...images);
  }
  function contains(target,x,y,tolerance){
    if(!target||!target.mask)return false;
    const reach=Math.ceil(tolerance/CELL);
    let cx=Math.floor(x/CELL),cy=Math.floor(y/CELL);
    for(let iy=Math.max(0,cy-reach);iy<=Math.min(GH-1,cy+reach);iy++)
      for(let ix=Math.max(0,cx-reach);ix<=Math.min(GW-1,ix+reach);ix++){
        if(!target.mask[iy*GW+ix])continue;
        const dx=(ix+.5)*CELL-x,dy=(iy+.5)*CELL-y;
        if(dx*dx+dy*dy<=tolerance*tolerance)return true;
      }
    return false;
  }
  return {one,contains,build,W,H};
})();