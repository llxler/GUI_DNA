const path = require('path');
const fs = require('fs');
const [dir, staging] = process.argv.slice(2).map(p=>path.resolve(p));
const webpack = require(path.join(staging,'node_modules/webpack'));
const entry = path.join(dir,'entry.js');
fs.writeFileSync(entry, "export {Form, Field} from 'react-final-form'; export {FORM_ERROR} from 'final-form';\n");
webpack({mode:'production', target:'web', entry, devtool:false, optimization:{minimize:false},
  resolve:{modules:[path.join(dir,'node_modules'),path.join(staging,'node_modules')]},
  externals:{react:'commonjs react'}, output:{path:dir,filename:'form-sdk.js',library:{type:'commonjs2'}}},
  (err,stats)=>{if(err || stats.hasErrors()){console.error(err || stats.toString({all:false,errors:true}));process.exitCode=1;}});
