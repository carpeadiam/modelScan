#!/usr/bin/env python3
"""Chronological training. No metrics are emitted unless a real held-out evaluation is possible."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score, average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from pipelineguard.features import FEATURES

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'dataset' / 'real_pipeline_history.csv'
if not path.exists(): raise SystemExit('No real dataset found. Collect completed Cloudflare builds first.')
df = pd.read_csv(path).sort_values('timestamp').drop_duplicates('cloudflare_build_uuid')
if len(df) < 30 or df.label.nunique() < 2:
    raise SystemExit(f'Insufficient real data for reliable training: {len(df)} rows, classes={df.label.value_counts().to_dict()}. Need at least 30 rows and both classes.')
# Chronological 70/15/15 split; keep identical commits in one partition.
unique = df.drop_duplicates('commit_sha').sort_values('timestamp')
cut1, cut2 = int(len(unique)*.70), int(len(unique)*.85)
train_commits = set(unique.iloc[:cut1].commit_sha)
val_commits = set(unique.iloc[cut1:cut2].commit_sha)
test_commits = set(unique.iloc[cut2:].commit_sha)
train = df[df.commit_sha.isin(train_commits)]; val = df[df.commit_sha.isin(val_commits)]; test = df[df.commit_sha.isin(test_commits)]
if min(len(train), len(val), len(test)) < 2 or train.label.nunique() < 2 or test.label.nunique() < 2:
    raise SystemExit('Chronological split does not contain enough examples/classes. Collect more distinct real commits.')
pre = ColumnTransformer([('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), FEATURES)], remainder='drop')
models = {
 'logistic_regression': Pipeline([('pre', pre), ('model', LogisticRegression(class_weight='balanced', max_iter=2000))]),
 'random_forest': Pipeline([('pre', pre), ('model', RandomForestClassifier(n_estimators=250, class_weight='balanced_subsample', min_samples_leaf=2, random_state=42))])
}
for m in models.values(): m.fit(train[FEATURES], train.label)
def evaluate(estimator):
 pred = estimator.predict(test[FEATURES]); prob = estimator.predict_proba(test[FEATURES])[:,1]
 return {'accuracy': accuracy_score(test.label,pred), 'precision': precision_score(test.label,pred,zero_division=0), 'recall': recall_score(test.label,pred,zero_division=0), 'f1': f1_score(test.label,pred,zero_division=0), 'confusion_matrix': confusion_matrix(test.label,pred,labels=[0,1]).tolist(), 'roc_auc': roc_auc_score(test.label,prob) if test.label.nunique()==2 else None, 'average_precision': average_precision_score(test.label,prob) if test.label.nunique()==2 else None}
all_metrics = {name: evaluate(estimator) for name, estimator in models.items()}
model = models['random_forest']; metrics = all_metrics['random_forest']
(ROOT/'artifacts').mkdir(exist_ok=True)
joblib.dump(model, ROOT/'artifacts'/'random_forest.joblib')
importance = dict(zip(FEATURES, model.named_steps['model'].feature_importances_.tolist()))
# Export forest trees in original input feature space. The worker evaluates raw features.
preprocessor = model.named_steps['pre']; scaler = preprocessor.named_transformers_['numeric'].named_steps['scale']; imputer = preprocessor.named_transformers_['numeric'].named_steps['impute']
trees=[]
for est in model.named_steps['model'].estimators_:
 t=est.tree_; trees.append({'children_left':t.children_left.tolist(),'children_right':t.children_right.tolist(),'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value[:,0,:].tolist()})
artifact={'feature_names':FEATURES,'imputer_medians':imputer.statistics_.tolist(),'scaler_mean':scaler.mean_.tolist(),'scaler_scale':scaler.scale_.tolist(),'trees':trees,'threshold':0.5}
(ROOT/'artifacts'/'model.json').write_text(json.dumps(artifact))
evaluation={'trained_at':pd.Timestamp.utcnow().isoformat(),'dataset_rows':len(df),'class_distribution':df.label.value_counts().to_dict(),'split_rows':{'train':len(train),'validation':len(val),'test':len(test)},'metrics':metrics,'model_comparison':all_metrics,'feature_importance':importance,'models_trained':['logistic_regression','random_forest'],'selected_model':'random_forest'}
(ROOT/'artifacts'/'evaluation.json').write_text(json.dumps(evaluation,indent=2))
print(json.dumps(evaluation,indent=2))
