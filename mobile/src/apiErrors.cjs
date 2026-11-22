function parseResponse(text,status){
 let payload;try{payload=JSON.parse(text);}catch{
  if(status===404)throw Error('The mobile account service is not deployed yet (HTTP 404). Ask the administrator to deploy the latest backend.');
  if(status===502||status===503||status===504)throw Error('The server is starting or unavailable (HTTP '+status+'). Please retry shortly.');
  if(status>=500)throw Error('The server could not complete this request (HTTP '+status+'). This is a server error, not a rejected form. Ask the administrator to check Railway logs and run studio_healthcheck.');
  if(status===403)throw Error('The server rejected this request (HTTP 403). Update the backend and retry.');
  throw Error('The server returned an unexpected response (HTTP '+status+'). Please retry.');
 }
 if(!payload||typeof payload!=='object'||Array.isArray(payload))throw Error('The server returned an unexpected response (HTTP '+status+').');
 return payload;
}
module.exports={parseResponse};
