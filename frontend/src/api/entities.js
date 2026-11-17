import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)}),quarantines:id=>api('/datasets/'+id+'/quarantines')};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const specs={list:()=>api('/specs'),create:data=>api('/specs',{method:'POST',body:JSON.stringify(data)})};
export const reversions={list:()=>api('/reversions'),create:data=>api('/reversions',{method:'POST',body:JSON.stringify(data)}),retry:id=>api('/reversions/'+id+'/retry',{method:'POST'})};
