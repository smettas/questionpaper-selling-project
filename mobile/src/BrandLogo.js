import React from 'react';
import {View,Image,useWindowDimensions} from 'react-native';
export function BrandLogo({compact=false}){
 const{width}=useWindowDimensions();const size=Math.min(compact?210:360,Math.max(80,width-(compact?104:80)));
 return <View style={{backgroundColor:'#fff',borderRadius:compact?10:16,padding:compact?5:8,alignSelf:compact?'flex-start':'center',marginVertical:compact?0:12}}><Image source={require('../assets/ojas-question-builder-logo.png')} accessibilityLabel="OJAS ONE Question Builder. JEE, NEET, KCET. Competitive Exam Paper Preparation." resizeMode="contain" style={{width:size,height:size*828/1900}}/></View>;
}
