import {createServer} from '../../artifacts/webbench-draw-runtime-20261117/node_modules/vite/dist/node/index.js';
const server = await createServer({configFile:false, root:process.argv[2],
  cacheDir:process.argv[3], logLevel:'error', clearScreen:false,
  optimizeDeps:{noDiscovery:true, include:[]},
  server:{host:'127.0.0.1', port:0, hmr:false, watch:null,
    fs:{strict:true, allow:[process.argv[2]]}}});
await server.listen();
console.log('READY ' + server.resolvedUrls.local[0]);
for (const signal of ['SIGINT','SIGTERM']) process.on(signal, async()=>{await server.close();process.exit(0);});
