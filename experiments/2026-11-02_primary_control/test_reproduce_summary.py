import copy, csv, tempfile, unittest
from pathlib import Path
import reproduce_summary as r

def fixture():
    rows=[]
    for i in range(1,160):
        for p,q,j in sorted(r.GRID):
            rows.append(dict(cluster_id=f'B{i:03d}',skeleton_id=f'family{(i-1)%12:02d}' if q!='R' else '',
                             context=p,response=q,judge=j,status='safe',label=0,historical_raw636_label=0 if q=='R' else None))
    return rows

def select(rows,b='B001',p='H',q='S',j='LG'):
    return next(x for x in rows if (x['cluster_id'],x['context'],x['response'],x['judge'])==(b,p,q,j))

class ReplayTests(unittest.TestCase):
    def test_exact_test(self):
        self.assertEqual(r.exact_mcnemar(0,0),1.0)
        self.assertEqual(r.exact_mcnemar(6,0),.03125)
        self.assertEqual(r.exact_mcnemar(0,6),.03125)
        self.assertEqual(r.exact_mcnemar(3,3),1.0)

    def test_paired_direction(self):
        out=r.paired([0,0,1],[1,1,0])
        self.assertEqual(out['table_rows_F_columns_S_0_1'],[[0,2],[1,0]])
        self.assertEqual(out['risk_difference_S_minus_F'],1/3)

    def test_incomplete_primary_suppresses_p(self):
        out=r.paired([0]*158,[1]*158,True)
        self.assertIsNone(out['exact_two_sided_mcnemar_p'])

    def test_zero_change_not_equivalence(self):
        out=r.paired([0]*159,[0]*159,True)
        self.assertEqual(out['nominal_paired_bootstrap95'],[0.,0.])
        self.assertAlmostEqual(out['any_paired_change_one_sided95_upper_under_sampling_model'],1-.05**(1/159))

    def test_complete_counts_and_directions(self):
        rows=fixture();x=select(rows);x['status']='unsafe';x['label']=1
        out=r.aggregate(rows)
        self.assertEqual(out['record_count'],1590)
        self.assertEqual(out['primary']['b_F0_S1'],1)
        self.assertEqual(out['primary']['c_F1_S0'],0)
        self.assertEqual(out['cells']['HS']['LG']['unsafe_count'],1)
        self.assertEqual(out['neutral']['risk_difference_S_minus_F'],0)

    def test_invalid_is_not_safe(self):
        rows=fixture();x=select(rows);x['status']='invalid';x['label']=None
        out=r.aggregate(rows)
        self.assertEqual(out['primary']['n'],158)
        self.assertIsNone(out['primary']['exact_two_sided_mcnemar_p'])
        self.assertEqual(out['cells']['HS']['LG']['valid_n'],158)
        self.assertEqual(out['primary_missing_or_invalid_cluster_ids'],['B001'])

    def test_missing_neutral_does_not_drop_primary(self):
        rows=fixture();x=select(rows,p='N');x['status']='missing';x['label']=None
        out=r.aggregate(rows)
        self.assertEqual(out['primary']['n'],159)
        self.assertEqual(out['neutral']['n'],158)
        self.assertEqual(out['record_count'],1589)

    def test_replay_direction(self):
        rows=fixture();x=select(rows,q='R');x['status']='unsafe';x['label']=1
        out=r.aggregate(rows)
        self.assertEqual(out['replay']['LG']['historical_rows_new_columns_0_1'],[[158,1],[0,0]])
        self.assertEqual(out['replay']['LG']['label_match_n'],158)

    def test_duplicate_rejected(self):
        rows=fixture();rows[-1]=copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError,'duplicate'): r.aggregate(rows)

    def test_bad_status_label_rejected(self):
        rows=fixture();rows[0]['status']='invalid'
        with self.assertRaisesRegex(ValueError,'status/label'): r.aggregate(rows)

    def test_csv_roundtrip_and_unexpected_column_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'rows.csv'
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=r.FIELDS);w.writeheader();w.writerows(fixture())
            self.assertEqual(r.load_rows(p),fixture())
            p.write_text(p.read_text().replace('historical_raw636_label','raw_response'))
            with self.assertRaisesRegex(ValueError,'unexpected columns'): r.load_rows(p)

    def test_manifest_digest_check(self):
        import hashlib,json
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'test.txt').write_text('frozen')
            (p/'MANIFEST.json').write_text(json.dumps({'files':{'test.txt':hashlib.sha256(b'frozen').hexdigest()}}))
            self.assertEqual(r.verify_manifest(p),1)
            (p/'test.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError,'manifest mismatch'): r.verify_manifest(p)

if __name__=='__main__':unittest.main()
