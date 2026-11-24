import React,{useEffect,useRef,useState} from 'react';
import {View,Text,Pressable,Animated,AccessibilityInfo} from 'react-native';
import {LinearGradient} from 'expo-linear-gradient';
import {MODE_CARDS} from './StudioParts';
import {colors} from './ui';

function TestCard({item,index,reduceMotion,disabled,onPress}){
 const enter=useRef(new Animated.Value(1)).current;
 const scale=useRef(new Animated.Value(1)).current;
 useEffect(()=>{
  if(reduceMotion){enter.setValue(1);scale.setValue(1);return;}
  enter.setValue(0);
  const animation=Animated.timing(enter,{toValue:1,duration:260,delay:index*45,useNativeDriver:true});
  animation.start();return()=>animation.stop();
 },[reduceMotion,index,enter,scale]);
 useEffect(()=>()=>scale.stopAnimation(),[scale]);
 const press=to=>{if(reduceMotion)return;Animated.spring(scale,{toValue:to,speed:28,bounciness:2,useNativeDriver:true}).start();};
 return <Animated.View style={{opacity:enter,transform:[{translateY:enter.interpolate({inputRange:[0,1],outputRange:[10,0]})},{scale}],marginBottom:10}}>
  <Pressable accessibilityRole="button" accessibilityLabel={item.title} accessibilityHint={item.description} accessibilityState={{disabled}} disabled={disabled} onPress={onPress} onPressIn={()=>press(.985)} onPressOut={()=>press(1)} style={({pressed})=>({backgroundColor:pressed?item.soft:'#fff',borderRadius:18,borderWidth:1,borderColor:pressed?item.color:'#e3e9ef',overflow:'hidden'})}>
   <View style={{flexDirection:'row',alignItems:'center',padding:16,minHeight:100}}>
    <LinearGradient colors={[item.soft,'#ffffff']} style={{width:48,height:52,borderRadius:14,alignItems:'center',justifyContent:'center',marginRight:14}}><Text style={{fontSize:20,fontWeight:'700',color:item.color}}>{item.code}</Text></LinearGradient>
    <View style={{flex:1}}><Text style={{fontSize:9,fontWeight:'700',letterSpacing:.7,color:item.color,marginBottom:5}}>{item.tag}</Text><Text style={{fontSize:17,fontWeight:'700',color:colors.ink,marginBottom:4}}>{item.title}</Text><Text style={{fontSize:12,lineHeight:18,color:colors.muted}}>{item.description}</Text></View>
    <Text style={{fontSize:24,color:item.color,marginLeft:10}}>›</Text>
   </View>
  </Pressable>
 </Animated.View>;
}
export function HomeTestCards({onChoose,onPatterns,patternCount=0,disabled=false}){
 // Keep content fully visible until the OS motion preference is known.
 const[reduceMotion,setReduceMotion]=useState(true);
 useEffect(()=>{
  let active=true,changed=false;
  const subscription=AccessibilityInfo.addEventListener('reduceMotionChanged',value=>{changed=true;if(active)setReduceMotion(value);});
  AccessibilityInfo.isReduceMotionEnabled().then(value=>{if(active&&!changed)setReduceMotion(value);}).catch(()=>{});
  return()=>{active=false;subscription.remove();};
 },[]);
 const patterns={id:'patterns',code:'06',title:'Saved patterns',tag:patternCount?patternCount+' SAVED':'YOUR QUESTION SEQUENCE',description:'Use a saved pattern or create a new one.',color:'#147f7b',soft:'#e6f4ee'};
 return <View>{[...MODE_CARDS,patterns].map((item,index)=><TestCard key={item.id} item={item} index={index} reduceMotion={reduceMotion} disabled={disabled} onPress={()=>item.id==='patterns'?onPatterns():onChoose(item.id)}/>)}</View>;
}
