export async function request<T=any>(path:string,options:RequestInit={}):Promise<T>{
 const token=localStorage.getItem('gucang-token');
 const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...options.headers}});
 if(!response.ok){const body=await response.json().catch(()=>({detail:'网络请求失败'}));if(response.status===401&&path!='/auth/login'){localStorage.removeItem('gucang-token');window.dispatchEvent(new Event('session-expired'));}throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
 return response.json();
}
export const post=(path:string,data:unknown)=>request(path,{method:'POST',body:JSON.stringify(data)});
export async function download(path:string,name:string){
 const response=await fetch('/api'+path,{headers:{Authorization:'Bearer '+localStorage.getItem('gucang-token')}});
 if(!response.ok)throw new Error('导出失败，请重试');
 const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);
}
