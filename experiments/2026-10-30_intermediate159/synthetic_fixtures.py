"""Neutral generated fixtures only: no research prompts, outputs or actual IDs.

Tests substitute these fixtures explicitly. Production hash guards are unchanged.
"""
import json
from pathlib import Path

LG_TEMPLATE='SYNTHETIC LG TEMPLATE; NOT A MODEL TOKENIZER TEMPLATE'


def source_rows():
    rows=[]
    for i in range(320):
        category='standard' if i<159 else 'contextual' if i<240 else 'copyright'
        # Match the 317-unique-text inventory using neutral repeated placeholders.
        text_index=i if i<317 else i-317
        rows.append({'BehaviorID':f'SYNTHETIC_{i:03d}', 'Behavior':f'Neutral synthetic task {text_index}',
                     'SemanticCategory':'synthetic', 'FunctionalCategory':category,
                     'Tags':'' if category=='standard' else 'synthetic-tag',
                     'ContextString':'Neutral synthetic context' if category=='contextual' else ''})
    blobs={}
    conditions={'FP16':'fp16','SP70':'sp70-multiseed','SP30':'sp30','SP40':'sp40',
                'SP50':'sp50-multiseed','SP55':'sp55-multiseed','SP60':'sp60-multiseed'}
    for condition,suffix in conditions.items():
        seeds=[42,123,2024] if condition in ('SP50','SP55','SP60') else [42]
        items=[{'index':i,'behavior':row['Behavior'],'category':row['SemanticCategory']} for i,row in enumerate(rows)]
        generations=[]
        for seed in seeds:
            responses=[f'Neutral synthetic answer {condition} seed {seed} row {i}' for i in range(320)]
            generations.append({'seed':seed,'responses':responses})
        blobs['raw/responses_sparsegpt-'+suffix+'.json']=json.dumps({'items':items,'n_behaviors':320,'seeds':seeds,'generations':generations}).encode()
        for evaluator,judge in [('HB','harmbench'),('LG','llamaguard')]:
            name='raw/safety_baseline_harmbench.json' if condition=='FP16' and evaluator=='HB' else 'raw/safety_sparsegpt-'+suffix+'_'+judge+'.json'
            evaluations=[]
            for generation in generations:
                samples=[dict(item,response=response,label=i%2) for i,(item,response) in enumerate(zip(items,generation['responses']))]
                evaluations.append({'seed':generation['seed'],'samples':samples})
            blobs[name]=json.dumps({'evaluations':evaluations}).encode()
    manifest={'synthetic_fixture':True}
    return rows,blobs,json.dumps(manifest).encode(),manifest


def bound_tasks(runner,condition=None):
    values=source_rows()
    return runner.bind_standard_tasks(*values) if condition is None else runner.bind_condition_tasks(*values,condition)


def scientific_references(runner):
    from research_parsers import VERSION
    result={}
    for evaluator in ('HB','LG'):
        model_id,revision=runner.MODELS[evaluator]
        template=runner.HB_TEMPLATE if evaluator=='HB' else LG_TEMPLATE
        result[evaluator]={'model_id':model_id,'model_revision':revision,'tokenizer_revision':revision,
            'template_sha256':runner.sha(template.encode()),'template':template,
            'settings':{'seed':42,'do_sample':False,'temperature_inactive':0,'top_p_inactive':1,
                        'max_new_tokens':1 if evaluator=='HB' else 128,'dtype':'float16','quantization':'none'},
            'token_policy':'HB right clip generation512 encode/decode, full prompt left2048; LG no truncate cap8192',
            'parser_version':VERSION,'parser_code_sha256':runner.sha(Path(runner.__file__).with_name('research_parsers.py').read_bytes())}
    return result
