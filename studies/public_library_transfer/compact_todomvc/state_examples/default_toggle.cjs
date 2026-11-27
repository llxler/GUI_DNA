({source, id, title}) => {
    localStorage.clear();
    const controller = Function(source + '\nreturn {init, reduce, select};')();
    const state = {todos:[{id,title,completed:false}],nextId:id+1,filter:'all',editing:null};
    const next = controller.reduce(state, {type:'toggle',id});
    const item=next.todos.find(row=>row.id===id && row.title===title);
    if (!item || typeof item.completed !== 'boolean') throw Error('Expected the same identified item');
    return item.completed;
}
