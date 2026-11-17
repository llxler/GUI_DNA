const fs=require('fs'), path=require('path'), http=require('http'), crypto=require('crypto');
const {spawn}=require('child_process');
const {chromium}=require('/opt/replay/node_modules/playwright');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n');
async function main(){
 const input=JSON.parse(fs.readFileSync('/inputs/inputs.json'));
 const browser=await chromium.launch({headless:true});
 save('/outputs/environment.json',{node:process.version,os:fs.readFileSync('/etc/os-release','utf8'),
  playwright:require('/opt/replay/node_modules/playwright/package.json').version,
  chromium:browser.version(),browser_sha256:hash(chromium.executablePath()),
  browser_executable:chromium.executablePath(),kernel:require('os').release()});
 await browser.close();
 for(const job of input.jobs){
  const folder='/inputs/pages/'+job.id,out='/outputs/scores/'+job.id;
  fs.mkdirSync(out,{recursive:true});
  if(fs.existsSync(out+'/report.json'))throw Error('Refuse to overwrite '+job.id);
  for(const [name,digest] of Object.entries(job.files))if(hash(path.join(folder,name))!==digest)throw Error('Source changed');
  const server=http.createServer((req,res)=>{
   const clean=decodeURIComponent(req.url.split('?')[0]),relative=clean==='/'?'index.html':clean.replace(/^\//,'');
   const file=path.resolve(folder,relative);
   if(!file.startsWith(folder+'/')||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}
   const type={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream';
   res.writeHead(200,{'Content-Type':type});fs.createReadStream(file).pipe(res);
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const args=['/opt/replay/node_modules/@playwright/test/cli.js','test','--config','playwright.config.cjs',
   ...job.specs.map(s=>'test/'+s+'.spec.js'),'--max-failures=1','--output',out+'/playwright-output'];
  const child=spawn(process.execPath,args,{cwd:'/opt/replay/harness/'+job.project,
   env:{...process.env,REPORT_FILE:out+'/report.json',EVAL_PROJECT_ROOT:folder,CANDIDATE_URL:'http://127.0.0.1:'+server.address().port,CI:'1'}});
  let stdout='',stderr='';child.stdout.on('data',d=>stdout+=d);child.stderr.on('data',d=>stderr+=d);
  const timer=setTimeout(()=>child.kill('SIGKILL'),900000);
  const code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve)});
  clearTimeout(timer);await new Promise(r=>server.close(r));
  fs.writeFileSync(out+'/stdout.txt',stdout);fs.writeFileSync(out+'/stderr.txt',stderr);
  if(!fs.existsSync(out+'/report.json'))throw Error('Missing report '+job.id);
  save(out+'/receipt.json',{exit_code:code,report_sha256:hash(out+'/report.json')});
  process.stdout.write(job.id+' complete\n');
 }
 save('/outputs/complete.json',{jobs:input.jobs.length,inputs_sha256:hash('/inputs/inputs.json')});
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exit(1)});
