import React,{createContext,forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {ScrollView,Keyboard,StyleSheet,Dimensions,Platform} from 'react-native';
const{targetOffset}=require('./keyboardGeometry.cjs');
export const KeyboardFocus=createContext(null);
// Scroll by the measured obstruction, rather than guessing which field is hidden.
export const KeyboardScroll=forwardRef(function KeyboardScroll(props,forwarded){
 const scroll=useRef(null),focus=useRef(null),offset=useRef(0),keyboardTop=useRef(null),timers=useRef([]);
 const[extra,setExtra]=useState(0);
 useImperativeHandle(forwarded,()=>scroll.current);
 function reveal(){
  const input=focus.current,host=scroll.current,viewport=host?.getNativeScrollRef?.()||host;
  if(!input?.measureInWindow||!viewport?.measureInWindow)return;
  input.measureInWindow((x,y,width,height)=>viewport.measureInWindow((sx,sy,sw,sh)=>{
   const next=targetOffset(y,height,sy,sh,keyboardTop.current,Dimensions.get('window').height,offset.current);
   if(Math.abs(next-offset.current)>1)host.scrollTo({y:next,animated:true});
  }));
 }
 function later(){for(const ms of [60,220])timers.current.push(setTimeout(reveal,ms));}
 function onField(input){focus.current=input;later();}
 useEffect(()=>{
  const show=e=>{keyboardTop.current=e.endCoordinates?.screenY??null;setExtra((e.endCoordinates?.height||0)+24);later();};
  const hide=()=>{keyboardTop.current=null;setExtra(0);};
  const a=Keyboard.addListener(Platform.OS==='ios'?'keyboardWillShow':'keyboardDidShow',show),b=Keyboard.addListener(Platform.OS==='ios'?'keyboardWillHide':'keyboardDidHide',hide);
  return()=>{a.remove();b.remove();timers.current.forEach(clearTimeout);};
 },[]);
 const style=StyleSheet.flatten(props.contentContainerStyle)||{};
 const base=style.paddingBottom??style.paddingVertical??style.padding??0;
 return <KeyboardFocus.Provider value={onField}><ScrollView {...props} ref={scroll} automaticallyAdjustKeyboardInsets={false} keyboardShouldPersistTaps={props.keyboardShouldPersistTaps||'handled'} keyboardDismissMode="on-drag" scrollEventThrottle={16} onScroll={e=>{offset.current=e.nativeEvent.contentOffset.y;props.onScroll?.(e);}} onContentSizeChange={(w,h)=>{props.onContentSizeChange?.(w,h);if(keyboardTop.current!==null)later();}} contentContainerStyle={[props.contentContainerStyle,{paddingBottom:base+extra}]}>{props.children}</ScrollView></KeyboardFocus.Provider>;
});
