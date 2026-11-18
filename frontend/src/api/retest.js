import {request,post} from './client.js';
export const retest={
 state:()=>request('/retest/state'),
 compile:()=>post('/retest/compile',{}),
 publish:()=>post('/retest/publish',{}),
 claim:x=>post('/retest/claim',x),
 quota:(id,quota)=>request(`/retest/studies/${id}/quota`,{method:'PUT',body:JSON.stringify({quota})}),
};
