// Projected body labels belong inside the model viewport, away from its controls.
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const intersects=(a,b)=>a.left<b.left+b.width&&a.left+a.width>b.left&&a.top<b.top+b.height&&a.top+a.height>b.top;
export function bodyMarkerLayout(width,height,markers,blocked=[]){
  const padding=8,gap=6,used=blocked.filter(b=>[b.left,b.top,b.width,b.height].every(finite)&&b.width>0&&b.height>0);
  return markers.map(marker=>{
    const {point,width:w,height:h}=marker;
    if(![width,height,w,h,point?.x,point?.y,point?.z].every(finite)||w<=0||h<=0||width<w+2*padding||height<h+2*padding
      ||Math.abs(point.x)>1||Math.abs(point.y)>1||Math.abs(point.z)>1)return null;
    const left=Math.max(padding,Math.min(width-w-padding,(point.x+1)*width/2-w/2));
    const top=Math.max(padding,Math.min(height-h-padding,(1-point.y)*height/2-h/2));
    const offsets=[[0,0],[0,h+gap],[0,-h-gap],[w+gap,0],[-w-gap,0],[0,2*(h+gap)],[0,-2*(h+gap)]];
    for(const [dx,dy] of offsets){
      const box={left:left+dx,top:top+dy,width:w,height:h};
      if(box.left<padding||box.top<padding||box.left+w>width-padding||box.top+h>height-padding)continue;
      if(used.some(b=>intersects(box,{left:b.left-gap/2,top:b.top-gap/2,width:b.width+gap,height:b.height+gap})))continue;
      used.push(box);return {left:box.left+w/2,top:box.top+h/2,box};
    }
    return null;
  });
}
