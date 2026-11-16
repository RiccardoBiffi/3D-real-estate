#!/usr/bin/env python3
"""Release regression fixtures; these do not certify a real model's geometry."""
import copy,hashlib,html,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('integration',Path(__file__).with_name('integrate-reviewed-models.py'))
integration=importlib.util.module_from_spec(spec);spec.loader.exec_module(integration)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.dist=self.root/'dist';self.work=self.root/'work'
        (self.dist/'modelli').mkdir(parents=True);(self.work/'models').mkdir(parents=True)
        self.omissions=['Garage presente nell’annuncio, non renderizzato.']
        metas={'creation-started':'2026-11-09T12:00:00+01:00','creation-finished':'2026-11-09T13:00:00+01:00','coverage':'partial','unrenderedVolumes':json.dumps(self.omissions,ensure_ascii=False)}
        body=''.join(f'<meta name="{k}" content="{html.escape(v,quote=True)}">' for k,v in metas.items())
        self.artifact=self.dist/'modelli/house.html';self.artifact.write_text(body)
        self.digest=hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.report={'id':'house','status':'ready','path':'modelli/house.html','views':[{'id':'exterior','label':'Esterno'},{'id':'terra','label':'Piano terra'}],
            'coverage':'partial','unrenderedVolumes':self.omissions,'notes':['Quote stimate.'],'sourcePlans':[],
            'verifiedAt':'2026-11-09T13:00:00+01:00','artifactSha256':self.digest,
            'qa':dict.fromkeys(('staticPassed','browserPassed','geometryPassed','orthographicPassed'),True),
            'fidelity':{'passed':True},'independentReview':{'passed':True,'artifactSha256':self.digest}}
        self.catalog={'updatedAt':'old','properties':[{'id':'house','title':'Casa','sourceUrls':['https://example.org/house'],
            'availability':{'status':'published','checkedAt':'old','reason':'Fonte leggibile'},
            'facts':{'priceEur':345000,'areaNotes':'90 m² casa, 40 taverna'},'historicalPrices':[{'priceEur':385000}],
            'model':{'status':'in_review','path':None,'views':[],'notes':['In revisione.']}}]}
    def tearDown(self):self.tmp.cleanup()
    def save_report(self):
        (self.work/'models/house-review.json').write_text(json.dumps(self.report))
    def run_integration(self,catalog=None,baseline=None):
        return integration.integrate(catalog or self.catalog,self.dist,self.work,baseline or {})
    def test_approval_preserves_every_non_model_field(self):
        before=copy.deepcopy(self.catalog);self.save_report();after,added=self.run_integration()
        self.assertEqual(added,['house']);self.assertEqual(self.catalog,before)
        for key,value in before['properties'][0].items():
            if key!='model':self.assertEqual(after['properties'][0][key],value)
        again,added=self.run_integration(after);self.assertEqual(again,after);self.assertEqual(added,[])
    def test_unreviewed_draft_does_not_become_public(self):
        self.report.pop('independentReview');self.save_report()
        after,added=self.run_integration();self.assertEqual(after,self.catalog);self.assertEqual(added,[])
    def test_stale_artifact_or_review_is_rejected(self):
        self.save_report();self.artifact.write_text(self.artifact.read_text()+'<!--changed-->')
        with self.assertRaises(ValueError):self.run_integration()
    def test_omissions_must_match_the_actual_html(self):
        self.report['unrenderedVolumes']=['Altri volumi omessi.'];self.save_report()
        with self.assertRaisesRegex(ValueError,'omitted volumes disagree'):self.run_integration()
    def test_archived_house_is_not_promoted(self):
        self.catalog['properties'][0]['availability']['status']='archived';self.save_report()
        after,added=self.run_integration();self.assertEqual(after,self.catalog);self.assertEqual(added,[])
    def test_baseline_requires_exact_metadata_and_html(self):
        self.save_report();catalog,_=self.run_integration();model=catalog['properties'][0]['model']
        (self.work/'models/house-review.json').unlink();baseline={'house':copy.deepcopy(model)}
        self.assertEqual(self.run_integration(catalog,baseline)[0],catalog)
        catalog['properties'][0]['model']['notes']=['Changed without new review.']
        with self.assertRaises(ValueError):self.run_integration(catalog,baseline)
        catalog['properties'][0]['model']=copy.deepcopy(baseline['house'])
        self.artifact.write_text(self.artifact.read_text()+'changed')
        with self.assertRaises(ValueError):self.run_integration(catalog,baseline)
    def test_carried_model_does_not_skip_fact_validation(self):
        self.save_report();catalog,_=self.run_integration();baseline={'house':copy.deepcopy(catalog['properties'][0]['model'])}
        (self.work/'models/house-review.json').unlink();catalog['properties'][0]['facts']['priceEur']=-1
        with self.assertRaises(ValueError):self.run_integration(catalog,baseline)
    def test_exterior_only_supports_one_real_view(self):
        self.report.update(coverage='exterior_only',views=[{'id':'exterior','label':'Esterno'}])
        self.report['qa']['orthographicPassed']=None
        self.artifact.write_text(self.artifact.read_text().replace('content="partial"','content="exterior_only"'))
        digest=hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.report['artifactSha256']=digest;self.report['independentReview']['artifactSha256']=digest;self.save_report()
        self.assertEqual(self.run_integration()[1],['house'])

if __name__=='__main__':unittest.main()
