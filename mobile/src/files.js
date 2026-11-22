import * as FS from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
let owner=null;export function setFileOwner(value){owner=value?String(value):null;}
const fileKey=()=> 'ojas.native.files.v1'+(owner?'.'+owner:'');const fileRoot=()=>FS.documentDirectory+'papers/'+(owner?'account-'+owner+'/':'');
export async function listFiles(){const key=fileKey(),root=fileRoot();let rows=[];try{rows=JSON.parse(await AsyncStorage.getItem(key)||'[]');}catch{}return rows.filter(r=>r.uri?.startsWith(root));}
export async function saveFiles(files){const key=fileKey(),root=fileRoot();
 if(!Array.isArray(files)||!files.length)throw Error('The server returned no files.');
 await FS.makeDirectoryAsync(root,{intermediates:true});const old=await listFiles(),saved=[];
 try{for(const f of files){if(typeof f.data!=='string'||!f.data.length||f.data.length>128*1024*1024)throw Error('Empty or oversized generated file.');if(!/\.(pdf|docx|csv)$/i.test(f.name))throw Error('Unsupported export format.');const name=f.name.replace(/[^\p{L}\p{N} ._-]/gu,'_');const uri=root+Crypto.randomUUID()+'-'+name;await FS.writeAsStringAsync(uri,f.data,{encoding:FS.EncodingType.Base64});saved.push({id:uri,name,uri,mime:f.type,created:Date.now()});}await AsyncStorage.setItem(key,JSON.stringify([...saved,...old]));return saved;}
 catch(e){await Promise.all(saved.map(f=>FS.deleteAsync(f.uri,{idempotent:true})));throw e;}
}
export async function shareFile(file){if(!await Sharing.isAvailableAsync())throw Error('No Android sharing service is available.');await Sharing.shareAsync(file.uri,{mimeType:file.mime,dialogTitle:file.name});}
export async function saveCopy(file){const access=await FS.StorageAccessFramework.requestDirectoryPermissionsAsync();if(!access.granted)return false;const uri=await FS.StorageAccessFramework.createFileAsync(access.directoryUri,file.name,file.mime);const bytes=await FS.readAsStringAsync(file.uri,{encoding:FS.EncodingType.Base64});await FS.writeAsStringAsync(uri,bytes,{encoding:FS.EncodingType.Base64});return true;}
export async function removeFile(file){const key=fileKey(),root=fileRoot();if(!file.uri.startsWith(root))throw Error('Invalid file.');await FS.deleteAsync(file.uri,{idempotent:true});await AsyncStorage.setItem(key,JSON.stringify((await listFiles()).filter(x=>x.id!==file.id)));}

// OJAS_FILE_OWNER_SNAPSHOT
