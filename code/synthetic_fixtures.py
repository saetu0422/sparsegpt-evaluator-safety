"""Neutral generated fixtures only; these are not the research observations."""
import json


def source_rows():
    rows=[]
    for i in range(320):
        category='standard' if i<159 else 'contextual' if i<240 else 'copyright'
        rows.append({'BehaviorID':f'SYNTHETIC_{i:03d}', 'Behavior':f'Neutral synthetic task {i}',
                     'SemanticCategory':'synthetic', 'FunctionalCategory':category,
                     'Tags':'' if category=='standard' else 'synthetic-tag',
                     'ContextString':'Neutral synthetic context' if category=='contextual' else ''})
    blobs={}
    for condition,suffix in [('FP16','fp16'),('SP70','sp70-multiseed')]:
        items=[{'index':i,'behavior':row['Behavior'],'category':row['SemanticCategory']} for i,row in enumerate(rows)]
        responses=[f'Neutral synthetic answer {condition} {i}' for i in range(320)]
        blobs['raw/responses_sparsegpt-'+suffix+'.json']=json.dumps({'items':items,'generations':[{'seed':42,'responses':responses}]}).encode()
        for evaluator,judge in [('HB','harmbench'),('LG','llamaguard')]:
            name='raw/safety_baseline_harmbench.json' if condition=='FP16' and evaluator=='HB' else 'raw/safety_sparsegpt-'+suffix+'_'+judge+'.json'
            samples=[dict(item,response=response,label=i%2) for i,(item,response) in enumerate(zip(items,responses))]
            blobs[name]=json.dumps({'evaluations':[{'seed':42,'samples':samples}]}).encode()
    manifest={'synthetic_fixture':True}
    return rows,blobs,json.dumps(manifest).encode(),manifest


def bound_tasks(runner):
    return runner.bind_standard_tasks(*source_rows())
