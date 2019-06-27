
from sklearn.metrics import accuracy_score, precision_score, f1_score, recall_score
import numpy as np

def get_preds(model, X_test, clf_thres=.5):
    """Performs binary classification based on the chosen probability/confidence level
    (clf_thres). For example, clf_thres=.9 means the model will predict category 1 only
    if it is at least 90% confident, else category 2."""
    y_pred = model.predict_proba(X_test)
    return np.array([0 if y[0] >= clf_thres else 1 for y in y_pred])

def score_model(y_true, y_pred, round_to=4, output='print'):
    """Scores a binary classification model in accuracy, precision, f1, and recall."""
    scores = {
        'accuracy': np.round(accuracy_score(y_true, y_pred), round_to),
        'precision': np.round(precision_score(y_true, y_pred), round_to),
        'f1': np.round(f1_score(y_true, y_pred), round_to),
        'recall': np.round(recall_score(y_true, y_pred), round_to)
    }
    
    if output == 'print':
        for score_name, score_val in scores.items():
            print(f'{score_name.title()}: {score_val}')
    elif output == 'dict':
        return scores

#To use human_readify, begin by defining your model_dict; here's an example:
# model_dict = { 
#    'KNN': knn, 'Logistic Regression': lr, 'Decision Tree': dt, 'Gradient Boosted
# Tree': gb,
#    'Random Forest': rf, 'Boostrap Aggregated Random Forest': bg
# }
def human_readify(model_dict):
    '''Returns an easy-to-read summary of models used and their scores.'''
    for model_name, model in model_dict.items():
        print(f'{model_name}:')
        y_pred = get_preds(model, X_test, clf_thres=.95)
        score_model(y_test, y_pred)
        print()
        
