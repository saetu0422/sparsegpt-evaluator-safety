#!/usr/bin/env python3
"""CPU-only exploratory R1/R2; consumes verified private JSON, emits no text."""
import argparse, collections, hashlib, json, os, platform, warnings
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/standard159_mpl')
import numpy as np
import pandas as pd
import scipy
from scipy import stats, optimize, special
from sklearn.model_selection import StratifiedKFold
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
CONDITIONS=['FP16','SP30','SP40','SP50','SP55','SP60','SP70']

def quality(text):
    if not isinstance(text,str): raise ValueError('Response must be string')
    w=[x.lower() for x in text.split()]; n=len(w)
    unique=len(set(w))/n if n else 0.
    dom=max(collections.Counter(w).values())/n if n else 0.
    legacy=1-len(set(zip(w,w[1:],w[2:])))/(n-2) if n>=3 else 0.
    return dict(words=n,unique_ratio=unique,repeat=legacy if n>=6 else 0.,legacy_repeat=legacy,dominance=dom,collapse=int((n>=50 and unique<.10) or (n>=50 and legacy>=.80) or (n>=20 and dom>=.30)))

def wilson(k,n):
    if not n:return [None,None]
    z=stats.norm.ppf(.975); p=k/n; d=1+z*z/n
    a=(p+z*z/(2*n))/d; b=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [float(a-b),float(a+b)]

def holm(ps):
    ps=np.asarray(ps); order=np.argsort(ps,kind='stable'); out=np.empty(len(ps));out[order]=np.minimum(1,np.maximum.accumulate(ps[order]*(len(ps)-np.arange(len(ps)))))
    return out.tolist()

def auc(y,p):
    y=np.asarray(y);n1=sum(y);n0=len(y)-n1
    if not n0 or not n1:return None
    return float((stats.rankdata(p)[y==1].sum()-n1*(n1+1)/2)/(n1*n0))

def bootmean(x,rng,B):
    x=np.asarray(x); return np.quantile(x[rng.integers(len(x),size=(B,len(x)))].mean(1),[.025,.975]).tolist() if len(x) else [None,None]

def summarize(x,rng,B):
    x=np.asarray(x)
    if not len(x):return {'n':0}
    return dict(n=len(x),mean=float(np.mean(x)),mean_ci95=bootmean(x,rng,B),median=float(np.median(x)),q1=float(np.quantile(x,.25)),q3=float(np.quantile(x,.75)),minimum=float(min(x)),maximum=float(max(x)),zero_count=int(sum(x==0)))

def separation(X,y):
    Z=X*(2*np.asarray(y)-1)[:,None]; p=X.shape[1]
    strict=optimize.linprog(np.zeros(p),A_ub=-Z,b_ub=-np.ones(len(y)),bounds=[(None,None)]*p,method='highs')
    if strict.success:return 'complete'
    # bounded homogeneous cone; nonnegative margins and positive total margin => quasi
    quasi=optimize.linprog(-Z.sum(0),A_ub=-Z,b_ub=np.zeros(len(y)),bounds=[(-1,1)]*p,method='highs')
    if quasi.success and -quasi.fun>1e-7:return 'quasi'
    return 'none' if strict.status==2 and quasi.success else 'indeterminate'

def logistic(X,y):
    X=np.asarray(X,float); y=np.asarray(y,float); mu=X.mean(0);sd=X.std(0)
    meta=dict(n=len(y),events=int(sum(y)),means=mu.tolist(),sds=sd.tolist())
    if np.any(sd==0) or len(set(y))<2:return dict(meta,status='constant_predictor_or_outcome'),None
    Z=np.column_stack([np.ones(len(y)),(X-mu)/sd]);sep=separation(Z,y);meta['separation']=sep
    if np.linalg.matrix_rank(Z)<Z.shape[1]:return dict(meta,status='rank_deficient'),None
    def fun(b):
        t=Z@b;return float(np.logaddexp(0,t).sum()-y@t)
    def jac(b):return Z.T@(special.expit(Z@b)-y)
    fit=optimize.minimize(fun,np.zeros(Z.shape[1]),jac=jac,method='BFGS',options={'gtol':1e-8,'maxiter':10000})
    b=fit.x;p=special.expit(Z@b);H=Z.T@((p*(1-p))[:,None]*Z);grad=float(np.max(np.abs(jac(b))));eig=np.linalg.eigvalsh(H)
    converged=bool(np.isfinite(b).all() and grad<1e-6 and eig.min()>1e-10)
    valid=converged and sep=='none'
    meta.update(status='ok' if valid else 'invalid_inference',optimizer_success=bool(fit.success),optimizer_message=str(fit.message),gradient_maxabs=grad,iterations=int(fit.nit),hessian_eigenvalues=eig.tolist(),hessian_condition=float(np.linalg.cond(H)),converged=converged,negative_loglikelihood=float(fit.fun),train_auc=auc(y,p),coefficient_names=['intercept','log_length','repeat','dominance'])
    if valid:
        cov=np.linalg.inv(H);T=np.zeros((4,4));T[0,0]=1;T[0,1:]=-mu/sd;T[1:,1:]=np.diag(1/sd);bo=T@b;co=T@cov@T.T
        for label,coef,vc in [('standardized',b,cov),('original_units',bo,co)]:
            se=np.sqrt(np.diag(vc));meta[label]={'coefficients':coef.tolist(),'se':se.tolist(),'ci95':np.column_stack([coef-1.959963984540054*se,coef+1.959963984540054*se]).tolist()}
    else:meta['diagnostic_only_coefficients']=b.tolist()
    return meta,(mu,sd,b) if valid else None

def r1(frame,rng,B):
    out={}; tests=[];summaries=[]
    for cond in CONDITIONS:
        f=frame[frame.condition==cond]; d=(f.LG.eq(1)&f.HB.eq(0)); a=~d
        item={'D_n':int(d.sum()),'A_n':int(a.sum()),'reverse_disagreement':int((f.LG.eq(0)&f.HB.eq(1)).sum()),'small_group_warning':bool(min(d.sum(),a.sum())<10),'metrics':{}}
        for m in ['words','repeat','dominance','collapse','legacy_repeat','unique_ratio']:
            xd=f.loc[d,m].to_numpy();xa=f.loc[a,m].to_numpy(); md={'D':summarize(xd,rng,B),'A':summarize(xa,rng,B)}
            for group in ['D','A']:summaries.append({'condition':cond,'metric':m,'group':group,**md[group]})
            if len(xd) and len(xa):
                u=stats.mannwhitneyu(xd,xa,alternative='two-sided',method='asymptotic',use_continuity=True)
                md.update(U=float(u.statistic),p=float(u.pvalue),rank_biserial=float(2*u.statistic/(len(xd)*len(xa))-1))
                tests.append({'condition':cond,'metric':m,'D_n':len(xd),'A_n':len(xa),'U':md['U'],'raw_p':md['p'],'rank_biserial':md['rank_biserial']})
            if m=='collapse':
                tab=[[int(xd.sum()),int(len(xd)-xd.sum())],[int(xa.sum()),int(len(xa)-xa.sum())]]; fs=stats.fisher_exact(tab) if len(xd) and len(xa) else None
                md.update(table=tab,Fisher_p=float(fs.pvalue) if fs else None,Fisher_odds_ratio=float(fs.statistic) if fs else None,Fisher_available=fs is not None,small_cell_warning=bool(min(sum(tab,[]))<5))
                for group,x in [('D',xd),('A',xa)]:md[group].update(proportion=float(x.mean()) if len(x) else None,wilson_ci95=wilson(int(x.sum()),len(x)))
            item['metrics'][m]=md
        out[cond]=item
    f=frame[frame.condition=='SP70'].copy();y=(f.LG.eq(1)&f.HB.eq(0)).astype(int).to_numpy();X=np.column_stack([np.log(np.maximum(f.words,1)),f.repeat,f.dominance]);model,_=logistic(X,y);model['zero_length_count']=int(sum(f.words==0));model['folds']=[];pred=np.full(len(y),np.nan);foldid=np.full(len(y),-1)
    for i,(tr,te) in enumerate(StratifiedKFold(n_splits=5,shuffle=True,random_state=42).split(X,y)):
        fm,fit=logistic(X[tr],y[tr]);fm.update(fold=i,test_n=len(te),train_n=len(tr),test_events=int(sum(y[te])),train_ids=f.iloc[tr].behavior_id.tolist(),test_ids=f.iloc[te].behavior_id.tolist());model['folds'].append(fm);foldid[te]=i
        if fit:
            mu,sd,b=fit;pred[te]=special.expit(np.column_stack([np.ones(len(te)),(X[te]-mu)/sd])@b)
    model['oof_valid']=bool(np.isfinite(pred).all());model['oof_auc']=auc(y,pred) if model['oof_valid'] else None
    model['oof_predictions']=[{'behavior_id':bid,'D':int(yy),'fold':int(ff),'probability':float(pp) if np.isfinite(pp) else None} for bid,yy,ff,pp in zip(f.behavior_id,y,foldid,pred)]
    out['SP70_logistic']=model
    out['any_disagreement_descriptive']=[{'condition':c,'group':g,'n':len(a),**{m:float(a[m].mean()) if len(a) else None for m in ['words','repeat','dominance','collapse']}} for c in CONDITIONS for g in ['disagree','agree'] for a in [frame[(frame.condition==c)&((frame.LG!=frame.HB) if g=='disagree' else (frame.LG==frame.HB))]]]
    return out,summaries,tests

def paired(frame,rng,B,comparisons):
    rows=[]
    for c0,c1 in comparisons:
        for j in ['LG','HB']:
            x=frame[frame.condition==c0].set_index('behavior_id')[j];y=frame[frame.condition==c1].set_index('behavior_id')[j].reindex(x.index);assert not y.isna().any();x=x.to_numpy();y=y.to_numpy();d=y-x;b=int(sum(d==1));c=int(sum(d==-1));ci=bootmean(d,rng,B)
            rows.append(dict(judge=j,comparison=f'{c0}→{c1}',baseline=c0,condition=c1,n=len(x),both_safe=int(sum((x==0)&(y==0))),b_safe_to_unsafe=b,c_unsafe_to_safe=c,both_unsafe=int(sum((x==1)&(y==1))),delta_pp=float(d.mean()*100),delta_bootstrap_ci95_pp=[v*100 for v in ci],raw_p=float(stats.binomtest(b,b+c,.5).pvalue) if b+c else 1.,small_discordant_warning=bool(b+c<10)))
    for row,p in zip(rows,holm([r['raw_p'] for r in rows])):row['holm_p']=p
    return rows

def agreement(frame,rng,B):
    rows=[]
    for c in CONDITIONS:
        f=frame[frame.condition==c];x=f.LG.to_numpy();y=f.HB.to_numpy();n=len(x);po=float(np.mean(x==y));pe=float(x.mean()*y.mean()+(1-x.mean())*(1-y.mean()));idx=rng.integers(n,size=(B,n));xx=x[idx];yy=y[idx];bp=(xx==yy).mean(1);be=xx.mean(1)*yy.mean(1)+(1-xx.mean(1))*(1-yy.mean(1));valid=be<1;bk=(bp[valid]-be[valid])/(1-be[valid]);tab=[[int(sum((x==a)&(y==b))) for b in [0,1]] for a in [0,1]]
        row=dict(condition=c,n=n,LG_unsafe=int(sum(x)),HB_unsafe=int(sum(y)),LG_rate=float(x.mean()),HB_rate=float(y.mean()),LG_wilson=wilson(sum(x),n),HB_wilson=wilson(sum(y),n),table_LGrows_HBcols_safe_unsafe=tab,agreement_count=int(sum(x==y)),agreement=po,agreement_wilson=wilson(sum(x==y),n),kappa=(po-pe)/(1-pe) if pe<1 else None,kappa_bootstrap_ci95=np.quantile(bk,[.025,.975]).tolist() if len(bk) else [None,None],kappa_undefined_bootstrap=B-len(bk),pabak=2*po-1,pabak_bootstrap_ci95=np.quantile(2*bp-1,[.025,.975]).tolist(),small_cell_warning=bool(min(sum(tab,[]))<5));rows.append(row)
    return rows

def safe_json(x):
    if isinstance(x,dict):return {k:safe_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe_json(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
    if isinstance(x,np.bool_):return bool(x)
    return x

def figures(frame,res,out):
    a=res['agreement'];xs=np.arange(7);fig,ax=plt.subplots(figsize=(8,4.8))
    for j,color in [('LG','#2563eb'),('HB','#b45309')]:
        rate=np.array([r[j+'_rate'] for r in a])*100;ci=np.array([r[j+'_wilson'] for r in a])*100
        ax.plot(xs,rate,'o-',label={'LG':'LlamaGuard','HB':'HarmBench'}[j],color=color);ax.fill_between(xs,ci[:,0],ci[:,1],color=color,alpha=.15)
    ax.set(xticks=xs,xticklabels=CONDITIONS,ylabel='Unsafe-label rate (%)',ylim=(-2,102),title='Final standard159: identical stored responses, two judges');ax.legend();ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(out/'figure1_rates.png',dpi=180);fig.savefig(out/'figure1_rates.pdf');plt.close(fig)
    f=frame[frame.condition=='SP70'];D=f.LG.eq(1)&f.HB.eq(0);fig,axs=plt.subplots(1,3,figsize=(10,3.8))
    for ax,m,title in zip(axs,['words','repeat','dominance'],['Whitespace words','Trigram repetition','Single-word dominance']):
        ax.boxplot([f.loc[~D,m],f.loc[D,m]],tick_labels=['A (n=37)','D (n=122)'],showmeans=True);ax.set_title(title);ax.grid(axis='y',alpha=.2)
    fig.suptitle('SP70 directional disagreement: descriptive quality distributions');fig.tight_layout();fig.savefig(out/'figure2_r1_quality.png',dpi=180);fig.savefig(out/'figure2_r1_quality.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5))
    for j,offset,color in [('LG',-.08,'#2563eb'),('HB',.08,'#b45309')]:
        rows=[r for r in res['r2_baseline12'] if r['judge']==j];v=np.array([r['delta_pp'] for r in rows]);ci=np.array([r['delta_bootstrap_ci95_pp'] for r in rows]);ax.errorbar(np.arange(6)+offset,v,yerr=np.array([v-ci[:,0],ci[:,1]-v]),fmt='o',capsize=3,label=j,color=color)
    ax.axhline(0,color='gray',lw=1);ax.set(xticks=np.arange(6),xticklabels=CONDITIONS[1:],ylabel='Change from FP16 (percentage points)',title='Paired changes; descriptive bootstrap 95% intervals');ax.legend();fig.tight_layout();fig.savefig(out/'figure3_baseline_deltas.png',dpi=180);fig.savefig(out/'figure3_baseline_deltas.pdf');plt.close(fig)

def main():
    ap=argparse.ArgumentParser();inputs=ap.add_mutually_exclusive_group(required=True);inputs.add_argument('--input',type=Path);inputs.add_argument('--metrics',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--bootstrap',type=int,default=20000);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    if args.metrics:
        frame=pd.read_csv(args.metrics,float_precision="round_trip")
        required=['condition','behavior_id','response_sha256','LG','HB','words','unique_ratio','repeat','legacy_repeat','dominance','collapse']
        assert list(frame.columns)==required, 'Unexpected metric columns'
        assert not frame.isna().any().any(), 'Missing metric values'
        assert (frame.words>=0).all() and (frame.words==np.floor(frame.words)).all()
        for m in ['unique_ratio','repeat','legacy_repeat','dominance']:assert frame[m].between(0,1).all()
        assert (frame.loc[frame.words<6,'repeat']==0).all()
        assert np.allclose(frame.loc[frame.words>=6,'repeat'],frame.loc[frame.words>=6,'legacy_repeat'])
        expected=((frame.words>=50)&(frame.unique_ratio<.10))|((frame.words>=50)&(frame.legacy_repeat>=.80))|((frame.words>=20)&(frame.dominance>=.30))
        assert (expected.astype(int)==frame.collapse).all(), 'Collapse inconsistent with metrics'
    else:
        data=json.loads(args.input.read_text());data=data['rows'] if isinstance(data,dict) else data
        rows=[]
        for r in data:rows.append({k:r[k] for k in ['condition','behavior_id','response_sha256','LG','HB']}|quality(r['response']))
        frame=pd.DataFrame(rows)
    frame['order']=frame.condition.map({c:i for i,c in enumerate(CONDITIONS)});frame=frame.sort_values(['order','behavior_id']).drop(columns='order').reset_index(drop=True)
    assert len(frame)==1113 and not frame.duplicated(['condition','behavior_id']).any();assert set(frame.condition)==set(CONDITIONS)
    ids=set(frame[frame.condition=='FP16'].behavior_id)
    for c in CONDITIONS:assert len(frame[frame.condition==c])==159 and set(frame[frame.condition==c].behavior_id)==ids
    assert set(frame.LG)|set(frame.HB)<={0,1};sp=frame[frame.condition=='SP70'];assert sum(sp.LG.eq(1)&sp.HB.eq(0))==122
    rng=np.random.default_rng(42);rr,summ,tests=r1(frame,rng,args.bootstrap)
    res=dict(schema='standard159-r1-r2-v1',exploratory=True,bootstrap_replicates=args.bootstrap,seed=42,methods_sha256=hashlib.sha256((Path(__file__).parent/'METHODS_FROZEN.md').read_bytes()).hexdigest(),input_sha256=hashlib.sha256((args.input or args.metrics).read_bytes()).hexdigest(),input_mode='private_text' if args.input else 'public_metrics',r1=rr,r2_baseline12=paired(frame,rng,args.bootstrap,[('FP16',c) for c in CONDITIONS[1:]]),adjacent10=paired(frame,rng,args.bootstrap,list(zip(CONDITIONS[1:-1],CONDITIONS[2:]))),agreement=agreement(frame,rng,args.bootstrap),environment={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'matplotlib':matplotlib.__version__})
    res=safe_json(res);(args.out/'results.json').write_text(json.dumps(res,indent=2,ensure_ascii=False,allow_nan=False)+'\n');frame.to_csv(args.out/'response_metrics_labels.csv',index=False)
    for name,rs in [('r1_summaries',summ),('r1_tests',tests),('r2_baseline12',res['r2_baseline12']),('adjacent10',res['adjacent10']),('agreement',res['agreement']),('logistic_oof',res['r1']['SP70_logistic']['oof_predictions'])]:pd.DataFrame(rs).to_csv(args.out/(name+'.csv'),index=False)
    coefficient_rows=[]
    model=res['r1']['SP70_logistic']
    for units in ['standardized','original_units']:
        if units in model:
            for i,name in enumerate(model['coefficient_names']):
                coefficient_rows.append(dict(units=units,term=name,coefficient=model[units]['coefficients'][i],se=model[units]['se'][i],ci95_low=model[units]['ci95'][i][0],ci95_high=model[units]['ci95'][i][1]))
    pd.DataFrame(coefficient_rows).to_csv(args.out/'logistic_coefficients.csv',index=False)
    sp70_rows=[]
    for metric in ['words','repeat','dominance','collapse']:
        m=res['r1']['SP70']['metrics'][metric]
        for group in ['D','A']:
            sp70_rows.append(dict(metric=metric,group=group,**m[group],U=m['U'],MWU_p=m['p'],rank_biserial=m['rank_biserial'],Fisher_p=m.get('Fisher_p')))
    pd.DataFrame(sp70_rows).to_csv(args.out/'r1_SP70_table.csv',index=False)
    figures(frame,res,args.out);print(json.dumps({'rows':len(frame),'SP70_D':rr['SP70']['D_n'],'logistic':res['r1']['SP70_logistic']['status'],'oof_auc':res['r1']['SP70_logistic']['oof_auc']},indent=2))
if __name__=='__main__':main()
