import { loadPyodide, type PyodideInterface } from 'pyodide';
import {retryableLoader} from './retryable-loader';
type Request={id:number;action:string;payload?:Record<string,unknown>};
const scope=self as unknown as DedicatedWorkerGlobalScope;
const boot=retryableLoader<PyodideInterface>(async()=>{
  const py=await loadPyodide({indexURL:new URL('../pyodide/',scope.location.href).href});
  py.FS.mkdirTree('/demo/ledgerly');
  for(const name of ['__init__.py','agent.py','extract.py','paypal.py']){
   const r=await fetch(new URL(`../python/ledgerly/${name}`,scope.location.href));if(!r.ok)throw new Error(`Python source ${name}: HTTP ${r.status}`);
   py.FS.writeFile(`/demo/ledgerly/${name}`,await r.text());
  }
  for(const name of ['bridge.py','review.py','invoice_details.py','review_history.py']){
   const source=await fetch(new URL(`../python/${name}`,scope.location.href));if(!source.ok)throw new Error(`Python demo ${name}: HTTP ${source.status}`);
   py.FS.writeFile(`/demo/${name}`,await source.text());
  }
  await py.runPythonAsync("import sys; sys.path.insert(0, '/demo'); import bridge");
  scope.postMessage({type:'ready'});return py;
});
async function run(request:Request):Promise<void>{
 try{const py=await boot();py.globals.set('request_json',JSON.stringify({action:request.action,...(request.payload||{})}));const result=await py.runPythonAsync('bridge.handle_json(request_json)');py.globals.delete('request_json');scope.postMessage({id:request.id,ok:true,data:JSON.parse(String(result))});}
 catch(error){scope.postMessage({id:request.id,ok:false,error:String(error)});}
}
let queue=Promise.resolve();scope.addEventListener('message',(event:MessageEvent<Request>)=>{const request=event.data;queue=queue.then(()=>run(request));});
