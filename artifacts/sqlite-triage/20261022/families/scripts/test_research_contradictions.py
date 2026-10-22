import contextlib
import csv
import io
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from flag_research_contradictions import main
from summarize_layer_review import read, write


class ContradictionTests(unittest.TestCase):
    def test_opposing_answers_are_retained_with_stable_ids_and_review_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=pathlib.Path(tmp);out=b/'layer-review-v3';out.mkdir();models=b/'joint-models-v3';models.mkdir()
            write(out/'pair_audit.csv',[dict(pair_id='1',contrast=.002,corner_counts='12|12|12|12',joint_finite_n=48,heldout_n=60)])
            write(out/'matched_context_contrasts.csv',[dict(pair_id='1',outcome='mid_price_change',horizon_s=120,
                fold=2,model='evotrees_depth3',matching='phase',stratum='before_start',feature_a='bid.size',
                feature_b='ask.size',contrast_min10=-.001,corner_counts='10|10|10|10',n=40)])
            write(out/'exact_pair_fold_stability.csv',[dict(opposite_signs_across_folds=False)])
            write(out/'all_ablation_summaries.csv',[dict(outcome='mid_price_change',horizon_s=120,
                source_group='book',helped_folds=1,hurt_folds=1,heldout_n=60,fold_deltas='.01|-.01',loss='mae')])
            metrics=[]
            for fold,mae in [(2,.5),(3,1.5)]:
                for model,loss in [('training_median',1),('evotrees_depth3',mae)]:
                    metrics.append(dict(outcome='mid_price_change',horizon_s=120,fold=fold,model=model,mae=loss,test_n=20))
            write(models/'all_model_fold_metrics.csv',metrics)
            write(models/'phase_direction_model_diagnostics.csv',[
                dict(outcome='mid_price_change',model=model,heldout_n=20,horizon_s=120,fold=2,phase='before_start',
                    prior_direction='up',mean_prediction=value,mean_observed=.001)
                for model,value in [('evotrees_depth3',.002),('neural_tree',-.001)]])
            with patch.dict(os.environ,FAMILY_RESEARCH_DIR=tmp,LAYER_REVIEW_VERSION='v3'), contextlib.redirect_stdout(io.StringIO()):
                main()
                flags=read(out/'contradiction_research_registry.csv')
                self.assertEqual(len(flags),4)
                self.assertEqual(len({r['research_id'] for r in flags}),4)
                self.assertTrue(all(r['answer_one'] and r['answer_two'] and r['support'] for r in flags))
                flags[0]['research_status']='under_scientific_review'
                write(out/'contradiction_research_registry.csv',flags)
                main()
                again=read(out/'contradiction_research_registry.csv')
                self.assertEqual({r['research_id'] for r in flags},{r['research_id'] for r in again})
                self.assertEqual(again[0]['research_status'],'under_scientific_review')


if __name__=='__main__':unittest.main()
