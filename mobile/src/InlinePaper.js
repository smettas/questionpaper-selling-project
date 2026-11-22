import React,{useEffect,useRef,useState} from 'react';
import {View,Text,FlatList,ActivityIndicator} from 'react-native';
import {api} from './api';
import {Question} from './Question';
import {Button,colors} from './ui';
const{locatePosition,TYPE_LABELS}=require('./patternTools.cjs');
export function InlinePaper({draft,busy,onReplace,onReport,header,footer}){
 const [cache,setCache]=useState({}),[errors,setErrors]=useState({}),[window,setWindow]=useState({start:0,end:6}),[retry,setRetry]=useState(0);
 const viewConfig=useRef({itemVisiblePercentThreshold:5}).current;
 const cacheRef=useRef({}),list=useRef(null),key=draft.question_ids.join(',');
 const lengthRef=useRef(draft.question_ids.length);lengthRef.current=draft.question_ids.length;
 useEffect(()=>{let current=true;const controller=new AbortController();const ids=draft.question_ids.slice(window.start,window.end).filter(id=>!cacheRef.current[id]);
  if(ids.length){api('studio-preview-batch',{data:{ids:ids.slice(0,12)},signal:controller.signal}).then(r=>{if(!current)return;const wanted=new Set(draft.question_ids);const next={...cacheRef.current,...Object.fromEntries(r.questions.filter(q=>wanted.has(q.id)).map(q=>[q.id,q]))};const visible=new Set(draft.question_ids.slice(window.start,window.end).map(String));const keep=[...Object.keys(next).filter(id=>!visible.has(id)).slice(-12),...visible];cacheRef.current=Object.fromEntries(keep.filter(id=>next[id]).map(id=>[id,next[id]]));setCache(cacheRef.current);setErrors(old=>{const copy={...old};for(const q of r.questions)delete copy[q.id];for(const f of r.failed||[])copy[f.id]=f.error;return copy;});}).catch(e=>{if(current)setErrors(old=>({...old,...Object.fromEntries(ids.map(id=>[id,e.message||'Could not load this question.']))}));});}
  return()=>{current=false;controller.abort();};
 },[key,window.start,window.end,retry]);
 const viewable=useRef(({viewableItems})=>{const indexes=viewableItems.map(v=>v.index).filter(Number.isInteger);if(!indexes.length)return;const start=Math.max(0,Math.min(...indexes)-1),end=Math.min(lengthRef.current,Math.max(...indexes)+3,start+12);setWindow(old=>old.start===start&&old.end===end?old:{start,end});}).current;
 return <FlatList ref={list} data={draft.questions} keyExtractor={q=>String(q.id)} extraData={{cache,errors,busy}} initialNumToRender={4} maxToRenderPerBatch={4} windowSize={5} keyboardShouldPersistTaps="handled" contentContainerStyle={{padding:18,paddingBottom:30}} onViewableItemsChanged={viewable} viewabilityConfig={viewConfig} ListHeaderComponent={header} ListFooterComponent={footer} renderItem={({item:q,index:i})=>{const p=locatePosition(draft.spec.sections,i),number=p?.number||i+1;return <View><View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginTop:8,marginBottom:8}}><Text style={{fontSize:12,color:colors.teal,fontWeight:'700'}}>{p?.label} · {TYPE_LABELS[p?.type]}</Text><Button compact quiet title={'Replace Q'+number} disabled={busy} onPress={()=>onReplace(i)}/></View>{errors[q.id]?<View style={{padding:18,borderWidth:1,borderColor:'#ebcbd0',backgroundColor:'#fff4f4',borderRadius:12,marginBottom:12}}><Text style={{color:colors.danger}}>Q{number}: {errors[q.id]}</Text><Button title="Retry question" onPress={()=>{setWindow({start:i,end:Math.min(i+6,draft.questions.length)});setRetry(n=>n+1);}}/></View>:<Question key={q.id} q={cache[q.id]} meta={q} readOnly position={number} onReport={()=>onReport(cache[q.id],q)}/>}</View>;}}/>;
}
