import hashlib
from test.compiler_reuse_audit.run import probe


def test_probe_snapshots_compiler_output_before_in_place_edit():
    package={'files':{'dependency.js':'original'},
        'compiler':'function compile(plan, files) {return {"index.html":"compiled"};}'}
    observed=probe(package,'function build(files, compile) {const output=compile({},files);output["index.html"]="modified";return output;}')
    assert observed['output_sha256']['index.html']==hashlib.sha256(b'modified').hexdigest()
    assert observed['calls'][0]['output_sha256']['index.html']==hashlib.sha256(b'compiled').hexdigest()
    assert observed['calls'][0]['input_files_sha256']['dependency.js']==hashlib.sha256(b'original').hexdigest()


def test_probe_records_modified_library_input_before_compile():
    package={'files':{'dependency.js':'original'},
        'compiler':'function compile(plan, files) {return {"index.html":files["dependency.js"]};}'}
    observed=probe(package,'function build(files, compile) {files["dependency.js"]="changed";return compile({flag:true},files);}')
    assert observed['calls'][0]['input_files_sha256']['dependency.js']==hashlib.sha256(b'changed').hexdigest()
    assert observed['calls'][0]['plan']=={'flag':True}


def test_json_snapshot_cannot_hide_nondata_plan_properties():
    package={'files':{'index.html':'original'},
        'compiler':'function compile(plan, files) {return {"index.html":"compiled"};}'}
    observed=probe(package,'function build(files, compile) {return compile({flag:true,callback:()=>1},files);}')
    assert observed['calls'][0]['plan']=={'flag':True}
    assert observed['calls'][0]['plan_data_only'] is False
