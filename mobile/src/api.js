const{parseResponse}=require('./apiErrors.cjs');
import {setFileOwner} from './files';
import * as SecureStore from 'expo-secure-store';
const BASE='https://questionpaper-selling-project-production.up.railway.app/api/mobile/v1/';
const KEY='ojas.native.token.v1';let token=null;let onUnauthorized=()=>{};
export const setUnauthorized=fn=>{onUnauthorized=fn;};
export async function restoreToken(){token=await SecureStore.getItemAsync(KEY);const owner=await SecureStore.getItemAsync(KEY+'.account');setFileOwner(owner);return !!token;}
export async function logout(){setFileOwner(null);await SecureStore.deleteItemAsync(KEY+'.account');token=null;await SecureStore.deleteItemAsync(KEY);}
export async function api(action,{data,query,form,timeout=45000,signal}={}){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);const abort=()=>controller.abort();signal?.addEventListener('abort',abort);
 try{
  const qs=query?Object.entries(query).flatMap(([k,v])=>(Array.isArray(v)?v:[v]).map(x=>encodeURIComponent(k)+'='+encodeURIComponent(x??''))).join('&'):'';
  const response=await fetch(BASE+action+'/'+(qs?'?'+qs:''),{method:data||form?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(data?{'Content-Type':'application/json'}:{})},body:form|| (data?JSON.stringify(data):undefined),signal:controller.signal});
  const text=await response.text();const payload=parseResponse(text,response.status);
  if(!response.ok){if(response.status===401&&!['login','studio-login','studio-register'].includes(action))onUnauthorized();throw Error(payload.error||'Request failed ('+response.status+').');}
  return payload;
 }catch(e){if(e.name==='AbortError')throw Error('Request interrupted or timed out. Check your connection and retry.');throw e;}finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
export async function login(username,password){const value=await api('login',{data:{username,password}});token=value.token;setFileOwner(value.account_id);await SecureStore.setItemAsync(KEY+'.account',String(value.account_id));await SecureStore.setItemAsync(KEY,token,{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});return value;}

export async function register(data){const value=await api('studio-register',{data});token=value.token;setFileOwner(value.account_id);await SecureStore.setItemAsync(KEY+'.account',String(value.account_id));await SecureStore.setItemAsync(KEY,token,{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});return value;}
