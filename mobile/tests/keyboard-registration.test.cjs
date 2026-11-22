const{test}=require('node:test');const assert=require('node:assert/strict');
const{parseResponse}=require('../src/apiErrors.cjs');const{targetOffset}=require('../src/keyboardGeometry.cjs');
test('HTTP 500 HTML identifies server failure without exposing the HTML',()=>{assert.throws(()=>parseResponse('<h1>secret traceback</h1>',500),e=>e.message.includes('HTTP 500')&&!e.message.includes('secret'));});
test('missing API and temporarily unavailable server are distinguished',()=>{assert.throws(()=>parseResponse('<html>',404),/not deployed/);assert.throws(()=>parseResponse('<html>',503),/unavailable/);});
test('field validation and successful signup JSON remain intact',()=>{assert.deepEqual(parseResponse('{"error":"Username unavailable"}',400),{error:'Username unavailable'});assert.equal(parseResponse('{"token":"test","account_id":1}',200).account_id,1);});
test('already visible field does not move',()=>{assert.equal(targetOffset(200,50,80,500,580,800,100),100);});
test('covered field scrolls above an overlay keyboard',()=>{assert.equal(targetOffset(650,50,80,700,500,800,100),324);});
test('resized Android viewport is respected as well as keyboard coordinates',()=>{assert.equal(targetOffset(450,50,80,350,500,800,100),194);});
test('a field above viewport scrolls upward and offset never goes negative',()=>{assert.equal(targetOffset(90,40,80,500,580,800,100),64);assert.equal(targetOffset(0,40,80,500,580,800,0),0);});
