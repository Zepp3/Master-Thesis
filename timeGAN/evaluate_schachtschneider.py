from table_evaluator import load_data, TableEvaluator
import pandas as pd
from sdv.evaluation import evaluate


def test_samples(database_name, print_data=False):

    test, fake = load_data('test_data_schachtschneider.csv', 'fake_data_' + database_name + '.csv')
    
    with pd.option_context('display.max_columns', None):
        if print_data:
            print(fake)

    with pd.option_context('display.max_columns', None):
        if print_data:
            print(test)
            
    cat_cols = ["public_holiday", "weekday"]
    table_evaluator = TableEvaluator(test, fake, cat_cols=cat_cols)
    table_evaluator.visual_evaluation()
    table_evaluator.evaluate(target_col='Lavandula', target_type='regr')
    print(evaluate(fake, test, aggregate=False))