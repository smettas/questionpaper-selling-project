function targetOffset(inputY,inputHeight,viewportY,viewportHeight,keyboardTop,windowHeight,offset){
 const bottom=Math.min(viewportY+viewportHeight,keyboardTop??windowHeight)-24;
 const delta=inputY+inputHeight>bottom?inputY+inputHeight-bottom:(inputY<viewportY+46?inputY-viewportY-46:0);
 return Math.max(0,offset+delta);
}
module.exports={targetOffset};
