export const pct=(n:number|undefined)=>((n??0)*100).toFixed(1)+'%';
export const decimal=(n:number|undefined)=>(n??0).toFixed(2);
export const date=(s:string)=>new Date(s).toLocaleString('zh-CN',{hour12:false});
export const names=(skus:string[],products:{sku:string;name:string}[])=>skus.map(s=>products.find(p=>p.sku===s)?.name||s).join(' + ');
