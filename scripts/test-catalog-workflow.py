#!/usr/bin/env python3
"""Regression fixtures for source errors, appended messages, identity and release guards."""
import copy,importlib.util,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path

HERE=Path(__file__).resolve().parent
def module(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
sources=module('check-sources');imports=module('import-chat-batch');release=module('release-state');builder=module('update-catalog');validator=module('validate-catalog')
staging=module('stage-release')

class Workflow(unittest.TestCase):
    def base(self):
        return {'chatId':'source','properties':[]},{'chatId':'source','messages':[]}
    def message(self,price=400000):
        text=f'Casa via Esempio 4 {price} https://example.org/annuncio/42/'
        prop={'id':'via-esempio-4','title':'Via Esempio4','address':'Via Esempio4','locality':'Trieste','sourceUrls':['https://example.org/annuncio/42/?utm_source=chat'],'chatFacts':{'priceEur':price,'description':'Casa indipendente.'},'evidenceQuote':text}
        return {'id':'same-message','turnId':'old-turn','role':'assistant','date':'2026-10-11','text':text,'properties':[prop]}
    def test_same_message_changes_and_repeat(self):
        inv,cp=self.base();batch={'chatId':'source','messages':[self.message()]};inv,cp,events=imports.merge(inv,cp,batch);self.assertEqual(len(events),1)
        again,again_cp,events=imports.merge(inv,cp,batch);self.assertEqual(again,inv);self.assertEqual(events,[])
        changed={'chatId':'source','messages':[self.message(390000)]};updated,cp,events=imports.merge(inv,cp,changed);self.assertEqual(len(updated['properties']),1);self.assertEqual(updated['properties'][0]['chatFacts']['priceEur'],390000);self.assertEqual(len(updated['properties'][0]['historicalPrices']),2)
        repeated,cp,events=imports.merge(updated,cp,changed);self.assertEqual(updated,repeated);self.assertEqual(events,[])
    def test_aliases_merge_without_fuzzy_street_match(self):
        inv,cp=self.base();msg=self.message();inv,cp,_=imports.merge(inv,cp,{'chatId':'source','messages':[msg]});msg['id']='second-message';msg['properties'][0]['id']='different-slug';inv,cp,_=imports.merge(inv,cp,{'chatId':'source','messages':[msg]});self.assertEqual(len(inv['properties']),1)
        msg['id']='third-message';msg['properties'][0]['id']='via-esempio-4';msg['properties'][0]['sourceUrls']=['https://example.net/other-house'];self.assertRaises(ValueError,imports.merge,inv,cp,{'chatId':'source','messages':[msg]})
    def test_evidence_and_chat_must_match(self):
        inv,cp=self.base();batch={'chatId':'wrong','messages':[self.message()]};self.assertRaises(ValueError,imports.merge,inv,cp,batch)
        batch['chatId']='source';batch['messages'][0]['properties'][0]['evidenceQuote']='not in the message';self.assertRaises(ValueError,imports.merge,inv,cp,batch)
    def test_blocked_and_removed_semantics(self):
        self.assertEqual(sources.conclude([{'state':'blocked','status':403}])[0],'unverified')
        self.assertEqual(sources.conclude([{'state':'removed','status':404}])[0],'unverified')
        self.assertEqual(sources.conclude([{'state':'removed','status':410}],exact_search_complete=True)[0],'unavailable')
        self.assertEqual(sources.conclude([{'state':'active'},{'state':'blocked'}])[0],'available')
        self.assertEqual(sources.conclude([{'state':'blocked'}],user_unavailable=True)[0],'unavailable')
    def test_failed_publication_preserves_last_valid(self):
        previous={'lastSuccessful':{'versionId':'old-native-version','catalogSha256':'old-hash'}};candidate={'commitSha':'new-sha','catalogSha256':'new-hash','checksPassed':True,'deployedFilesMatched':False};failed={'id':'native-deployment','version_id':'native-version','status':'failed','failure_message':'fixture upload failure'}
        result=release.record(previous,candidate,failed);self.assertEqual(result['lastSuccessful'],previous['lastSuccessful']);self.assertEqual(result['lastAttempt']['status'],'failed');self.assertEqual(previous,{'lastSuccessful':{'versionId':'old-native-version','catalogSha256':'old-hash'}})
        failed.update(status='succeeded',url='https://example.org');self.assertRaises(ValueError,release.record,previous,candidate,failed)
    def test_confirmed_archive_survives_errors_but_active_listing_reopens(self):
        self.assertEqual(sources.conclude([{'state':'blocked'}],previous_unavailable=True)[0],'unavailable')
        self.assertEqual(sources.conclude([{'state':'uncertain'}],previous_unavailable=True)[0],'unavailable')
        self.assertEqual(sources.conclude([{'state':'active'}],previous_unavailable=True)[0],'available')
    def test_search_collection_cannot_prove_an_exact_listing_is_active(self):
        class Response:
            status=200
            def __init__(self,url):self.url=url
            def read(self,*args):return b'<html>price EUR 519000; camere; superficie</html>'
            def __enter__(self):return self
            def __exit__(self,*args):pass
        examples=[('https://www.idealista.it/vendita-case/muggia-trieste/con-ville/','uncertain'),('https://www.idealista.it/geo/vendita-case/fontanella/','uncertain'),('https://www.idealista.it/immobile/35710865/','active'),('https://www.tecnocasa.it/vendita/ville/trieste/trieste/61221689.html','active')]
        for url,expected in examples:
            with patch.object(sources,'urlopen',return_value=Response(url)):
                self.assertEqual(sources.check(url)['state'],expected)
    def test_archive_and_last_active_evidence_survive_repeated_blocked_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prop={'id':'house','sourceUrls':['https://example.org/house']};path=root/'house.json'
            with patch.object(sources,'check',return_value={'state':'blocked'}),patch.object(sources.time,'sleep'):
                path.write_text(json.dumps({'conclusion':'unavailable','checkedAt':'2026-10-11T12:00:00+02:00'}))
                self.assertEqual(sources.run(prop,root)['conclusion'],'unavailable')
                self.assertEqual(sources.run(prop,root)['conclusion'],'unavailable')
                path.write_text(json.dumps({'conclusion':'available','checkedAt':'2026-10-13T12:00:00+02:00'}))
                for _ in range(2):
                    result=sources.run(prop,root)
                    self.assertEqual(result['conclusion'],'unverified')
                    self.assertEqual(result['lastConfirmedAvailability']['checkedAt'],'2026-10-13T12:00:00+02:00')
    def test_unverified_and_archived_listings_keep_last_observed_facts(self):
        inv,cp=self.base();inv,cp,_=imports.merge(inv,cp,{'chatId':'source','messages':[self.message()]})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'live-facts').mkdir();(root/'source-checks').mkdir()
            (root/'live-facts/via-esempio-4.json').write_text(json.dumps({'checkedAt':'2026-10-13T12:00:00+02:00','facts':{'priceEur':345000,'parking':'Box'},'sourceUrls':['https://example.org/annuncio/42/']}))
            for status in ('available','unverified','unavailable'):
                (root/'source-checks/via-esempio-4.json').write_text(json.dumps({'conclusion':status,'checkedAt':'2026-10-18T12:00:00+02:00'}))
                prop=builder.catalog(inv,root,{})[0]
                self.assertEqual(prop['facts']['priceEur'],345000)
                self.assertEqual(prop['facts']['parking'],'Box')
                self.assertEqual(prop['evidence']['listingReadAt'],'2026-10-13T12:00:00+02:00')
                self.assertEqual(prop['availability']['status'],status)
    def test_dates_alone_are_quiet(self):
        before={'properties':[{'id':'house','facts':{'priceEur':100},'availability':{'status':'unverified','checkedAt':'old'},'model':{'status':'awaiting_plans'}}]};after=copy.deepcopy(before);after['properties'][0]['availability']['checkedAt']='new';self.assertEqual(release.meaningful_changes(before,after),[])
        after['properties'][0]['facts']['priceEur']=90;self.assertEqual(release.meaningful_changes(before,after),[{'id':'house','kind':'facts'}])
    def test_missing_plan_and_unreviewed_model_are_hidden(self):
        inv,cp=self.base();inv,cp,_=imports.merge(inv,cp,{'chatId':'source','messages':[self.message()]})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'models').mkdir();(root/'models/via-esempio-4-review.json').write_text(json.dumps({'status':'ready','path':'modelli/fake.html'}));properties=builder.catalog(inv,root,{});self.assertIsNone(properties[0]['model']['path']);self.assertEqual(properties[0]['model']['status'],'awaiting_plans')
    def test_partial_model_requires_visible_omissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'modelli').mkdir();(root/'modelli/partial.html').write_text('<meta name="creation-finished" content="2026-10-12">')
            prop={'id':'partial','sourceUrls':[],'availability':{'status':'unverified'},'model':{'status':'ready','path':'modelli/partial.html','coverage':'partial','verifiedAt':'2026-10-12','views':[{},{}],'unrenderedVolumes':[]}}
            self.assertIn('partial: partial model without omitted-volume disclosure',validator.validate({'properties':[prop]},root))
            prop['model']['unrenderedVolumes']=['Garage presente nell’annuncio, non renderizzato.']
            self.assertEqual(validator.validate({'properties':[prop]},root),[])
            before={'properties':[copy.deepcopy(prop)]};prop['model']['unrenderedVolumes']=['Garage e cantina non renderizzati.']
            self.assertTrue(release.meaningful_changes(before,{'properties':[prop]}))
    def test_release_excludes_drafts_and_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dist=root/'dist';dist.mkdir();(dist/'assets').mkdir();(dist/'data').mkdir();(dist/'modelli').mkdir()
            for name in ('index.html','app.js','styles.css','assets/favicon.svg'):(dist/name).write_text('fixture')
            (dist/'data/catalog.json').write_text(json.dumps({'properties':[]}));(dist/'modelli/draft.html').write_text('unfinished');(dist/'private.txt').write_text('private')
            staging.stage(dist,root/'out',root/'work')
            self.assertFalse((root/'out/modelli/draft.html').exists());self.assertFalse((root/'out/private.txt').exists());self.assertTrue((root/'out/source-integrity.json').exists())

if __name__=='__main__':unittest.main()
