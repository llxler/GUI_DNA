const config = __FEATURE_CONFIG__;
const {Form, Field, FORM_ERROR} = sdk;
const fieldValue = (obj,key) => key.split('.').reduce((a,b) => a == null ? undefined : a[b], obj);
function bind(str, ctx) {
  if (typeof str !== 'string') return str;
  const exact = str.match(/^\{([\w.]+)\}$/);
  if (exact) return fieldValue(ctx,exact[1]) ?? '';
  return str.replace(/\{([\w.]+)\}/g,(token,key)=>String(fieldValue(ctx,key) ?? ''));
}
export default function ConfiguredForm(props) {
  const [server, setServer] = React.useState({});
  const currentAction = React.useRef(0);
  const submitted = React.useRef(null);
  const prefix = React.useId();
  const send = async values => {
    const action=config.actions[currentAction.current];
    const ctx={values,props:{...config.defaults,...props}};
    const request={method:action.method};
    if (!['GET','HEAD'].includes(action.method)) {
      request.headers={'Content-Type':'application/json'};
      const entries=Object.entries(action.body || {}).map(([k,v])=>[k,bind(v,ctx)]);
      request.body=JSON.stringify(Object.fromEntries(entries));
    }
    try {
      const response=await fetch(bind(action.url,ctx),request);
      let data={};
      try { data=await response.json(); } catch {}
      setServer(data || {});
      if (!response.ok) return {[FORM_ERROR]:bind(action.error,{...ctx,data}) || 'Request failed'};
    } catch { return {[FORM_ERROR]:bind(action.error,ctx) || 'Network error'}; }
  };
  return <Form onSubmit={send} initialValues={Object.fromEntries(config.fields.map(f=>[f.name,f.initial ?? '']))}
    render={form=><Fields form={form} active={currentAction} submitted={submitted} server={server} prefix={prefix} supplied={props} />} />;
}
function Fields({form,active,submitted,server,prefix,supplied}) {
  React.useEffect(()=>{
    if (config.onMount && submitted.current===null) {submitted.current=0;active.current=0;form.form.submit();}
  },[form.form,active,submitted]);
  const action=config.actions[submitted.current ?? 0];
  const ctx={values:form.values,props:{...config.defaults,...supplied},data:server};
  return <form onSubmit={form.handleSubmit}>
    {config.fields.map(f=>{
      const id=prefix+'-'+f.name;
      const attrs={id,'data-testid':f.testId || undefined,placeholder:f.placeholder || undefined};
      return <React.Fragment key={f.name}>{f.label && <label htmlFor={id}>{f.label}</label>}
        <Field name={f.name} parse={v=>v} render={({input})=> f.type==='select' ?
          <select {...attrs} {...input}><option value=""/>{(f.options||[]).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select> :
          f.type==='textarea' ? <textarea {...attrs} {...input}/> : <input {...attrs} {...input} type={f.type || 'text'}/>} />
      </React.Fragment>;
    })}
    {config.actions.map((a,i)=>a.label && <button key={i} data-testid={a.testId || undefined}
      type="submit" onClick={()=>{active.current=i;submitted.current=i;}}>{a.label}</button>)}
    {form.submitFailed && <p>{form.submitError}</p>}
    {form.submitSucceeded && <p>{bind(action.success,ctx)}</p>}
    {(form.submitSucceeded ? action.output || [] : []).map((s,i)=><p key={i}>{bind(s,ctx)}</p>)}
  </form>;
}
