const fs = require('node:fs');
const vm = require('node:vm');
const {source, cases} = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(({state, filters}) => {
  const rows = JSON.stringify(state.todos);
  state.todos.forEach(Object.freeze);
  Object.freeze(state.todos);
  const context = vm.createContext({state, filters, localStorage: {setItem() {}}});
  try {
    const observations = vm.runInContext(source + `
       filters.map(filter => {
         state = route(state, {type:'route', filter});
         return {filter:state.filter, rows:JSON.stringify(state.todos), editing:state.editing, nextId:state.nextId};
       })`, context, {timeout:100});
    const passed = observations.every((v,i) => v.filter === filters[i] && v.rows === rows &&
                                             v.editing === state.editing && v.nextId === state.nextId);
    return {passed, observations};
  } catch (e) {
    return {passed:false,error:String(e).slice(0,180)};
  }
});
process.stdout.write(JSON.stringify(results));
