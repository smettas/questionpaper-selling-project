import * as SecureStore from 'expo-secure-store';
const BASE='https://questionpaper-selling-project-production.up.railway.app/api/mobile/v1/';
const KEY='ojas.native.token.v1';let token=null;let onUnauthorized=()=>{};
export const setUnauthorized=fn=>{onUnauthorized=fn;};
export async function restoreToken(){token=await SecureStore.getItemAsync(KEY);return !!token;}
export async function logout(){token=null;await SecureStore.deleteItemAsync(KEY);}
export async function api(action,{data,query,form,timeout=45000,signal}={}){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);const abort=()=>controller.abort();signal?.addEventListener('abort',abort);
 try{
  const qs=query?Object.entries(query).flatMap(([k,v])=>(Array.isArray(v)?v:[v]).map(x=>encodeURIComponent(k)+'='+encodeURIComponent(x??''))).join('&'):'';
  const response=await fetch(BASE+action+'/'+(qs?'?'+qs:''),{method:data||form?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(data?{'Content-Type':'application/json'}:{})},body:form|| (data?JSON.stringify(data):undefined),signal:controller.signal});
  const text=await response.text();let payload;try{payload=JSON.parse(text);}catch{throw Error(response.status===404?'Mobile API is not deployed yet. Install the backend patch first.':'The server returned an invalid response.');}
  if(!response.ok){if(response.status===401&&action!=='login')onUnauthorized();throw Error(payload.error||'Request failed ('+response.status+').');}
  return payload;
 }catch(e){if(e.name==='AbortError')throw Error('Request interrupted or timed out. Check your connection and retry.');throw e;}finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
export async function login(username,password){const value=await api('login',{data:{username,password}});token=value.token;await SecureStore.setItemAsync(KEY,token,{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});return value;}
