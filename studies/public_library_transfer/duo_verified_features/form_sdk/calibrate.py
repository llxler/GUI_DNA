from . import setup
from .. import diagnose, prepare as p

def run():
    cfg=dict(fields=[dict(name="title",type="text",label="Title")],defaults=dict(shelf="1"),
             actions=[dict(label="Store book",method="POST",url="/calibration/books/{props.shelf}",
                           body={"title":"{values.title}"},success="Saved {data.title}",error="Could not save")])
    result=diagnose.probe("third-party-sdk",setup.HERE/"transport.test.js",setup.source(cfg))
    p.save(setup.OUT/"calibration.json",result)

if __name__=="__main__":run()
