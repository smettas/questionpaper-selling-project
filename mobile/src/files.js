import * as FS from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
const KEY='ojas.native.files.v1';const ROOT=FS.documentDirectory+'papers/';
export async function listFiles(){let rows=[];try{rows=JSON.parse(await AsyncStorage.getItem(KEY)||'[]');}catch{}return rows.filter(r=>r.uri?.startsWith(ROOT));}
export async function saveFiles(files){
 if(!Array.isArray(files)||!files.length)throw Error('The server returned no files.');
 await FS.makeDirectoryAsync(ROOT,{intermediates:true});const old=await listFiles(),saved=[];
 try{for(const f of files){if(typeof f.data!=='string'||!f.data.length||f.data.length>128*1024*1024)throw Error('Empty or oversized generated file.');if(!/\.(pdf|docx)$/i.test(f.name))throw Error('Unsupported export format.');const name=f.name.replace(/[^\p{L}\p{N} ._-]/gu,'_');const uri=ROOT+Crypto.randomUUID()+'-'+name;await FS.writeAsStringAsync(uri,f.data,{encoding:FS.EncodingType.Base64});saved.push({id:uri,name,uri,mime:f.type,created:Date.now()});}await AsyncStorage.setItem(KEY,JSON.stringify([...saved,...old]));return saved;}
 catch(e){await Promise.all(saved.map(f=>FS.deleteAsync(f.uri,{idempotent:true})));throw e;}
}
export async function shareFile(file){if(!await Sharing.isAvailableAsync())throw Error('No Android sharing service is available.');await Sharing.shareAsync(file.uri,{mimeType:file.mime,dialogTitle:file.name});}
export async function saveCopy(file){const access=await FS.StorageAccessFramework.requestDirectoryPermissionsAsync();if(!access.granted)return false;const uri=await FS.StorageAccessFramework.createFileAsync(access.directoryUri,file.name,file.mime);const bytes=await FS.readAsStringAsync(file.uri,{encoding:FS.EncodingType.Base64});await FS.writeAsStringAsync(uri,bytes,{encoding:FS.EncodingType.Base64});return true;}
export async function removeFile(file){if(!file.uri.startsWith(ROOT))throw Error('Invalid file.');await FS.deleteAsync(file.uri,{idempotent:true});await AsyncStorage.setItem(KEY,JSON.stringify((await listFiles()).filter(x=>x.id!==file.id)));}
