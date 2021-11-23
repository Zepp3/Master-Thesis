from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import joblib
import numpy as np
import pandas as pd
import warnings
import time
import optuna
from timegan import timegan
from own_data_loading_MonthlyMilkProduction import real_data_loading, preprocess_data, cut_data
from sdv.evaluation import evaluate
from table_evaluator import load_data, TableEvaluator
import argparse
import tensorflow as tf
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


def postprocess_data(eval_or_opt, generated_data, columns, seq_len, *shift_numbers):
    """
    Postprocesses synthesized data
    :param eval_or_opt: "opt" for the optimization loop, "eval" for training the optimized model
    :param generated_data: synthesized data from the model
    :param columns: Names of the columns of the dataset
    :param num_columns_cat: number of categorical columns
    :param seq_len: sequence length
    :shift_numbers: number of days for which the dataset should be shifted. Can be multiple days as well as positive and negative
    :return: postprocessed fake data
    """       
    # delete shifted data
    if shift_numbers != (0,):
        generated_data = generated_data[:,:,:len(shift_numbers) * -1]

    
    conditioned_dataset = []
    for i in range(np.shape(generated_data)[0]):
        for j in range(np.shape(generated_data)[1]):
            conditioned_dataset.append(generated_data[i,j,:])
    
    # transform to a pandas dataframe
    generated_data_df = pd.DataFrame(data=conditioned_dataset, columns=columns)
    
    
    fake_data = generated_data_df
        
    return fake_data


best_scores = 0

def objective(trial, dataset_train, dataset_val, num_samples, columns, database_name, *shift_numbers):
    """
    Objective function for hyperparameter optimization with optuna
    :param trail: current optimization trial
    :param dataset_train: training data
    :param dataset_val: validation data
    :param num_samples: number of fake samples that should be generated
    :param columns: column names
    :param num_columns_cat: number of categorical columns   
    :param database_name: name of the project
    :param shift_numbers: number of days for which the dataset should be shifted. Can be multiple days as well as positive and negative
    :return: score of the optimization
    """      
    if trial.number == 60:
        trial.study.stop()
    
    # hyperparameters
    module = trial.suggest_categorical("module", ["gru", "lstm", "lstmLN"])
    hidden_dim = trial.suggest_categorical("hidden_dim", [6, 12, 24, 48])
    batch_size = trial.suggest_categorical("batch_size", [2, 4, 8])
    num_layer = trial.suggest_int("num_layer", 3, 6, 1)
    iterations = trial.suggest_categorical("iterations", [100, 1000, 10000])
    seq_len = trial.suggest_categorical("seq_len", [1, 5, 10])
    

    data = cut_data(dataset_train, seq_len)
    
    # set timeGAN parameters
    parameters = dict()
    parameters['module'] = module
    parameters['hidden_dim'] = hidden_dim
    parameters['num_layer'] = num_layer
    parameters['iterations'] = iterations
    parameters['batch_size'] = batch_size
    parameters['seq_len'] = seq_len
    
    # generate data
    print(np.shape(data))
    print(seq_len)
    print(batch_size)
    generated_data = timegan(data, parameters)

    # postprocessing
    fake_data = postprocess_data("opt", generated_data, columns, seq_len, *shift_numbers)

    # calculate score
    scores = evaluate(fake_data, dataset_val)
    
    # save best model
    global best_scores
    if scores > best_scores:
        joblib.dump(timegan, database_name + '.gz')
        objective.seq_len = seq_len
        objective.parameters = parameters
        best_scores = scores

    return scores


def run_TimeGAN(num_samples, n_trials, database_name, *shift_numbers):
    """
    Run timeGAN
    :param num_samples: number of fake samples that should be generated
    :param n_trials: number of optimization trials
    :param database_name: name of the project
    :param shift_numbers: number of days for which the dataset should be shifted. Can be multiple days as well as positive and negative
    """
    # load data
    dataset = real_data_loading()

    # preprocess data
    dataset_train, columns, dataset_val, dataset, shift_numbers = preprocess_data(dataset, database_name, *shift_numbers)
    
    # optimize hyperparameters
    study = optuna.create_study(storage=optuna.storages.RDBStorage("sqlite:///" + database_name + ".db"), 
                                study_name = database_name + "_study", direction="maximize", load_if_exists=True)  #  use GP
    study.optimize(lambda trial: objective(trial,dataset_train, dataset_val, num_samples, columns, database_name, *shift_numbers), n_trials)
    
    # save performance parameters
    performance = open("performance_" + database_name + ".txt","w+")
    best_parameters = str(study.best_params)
    performance.write(best_parameters)
    best_values = str(study.best_value)
    performance.write(best_values)
    best_trials = str(study.best_trial)
    performance.write(best_trials)
    
    # plots of optuna optimization
    fig1 = optuna.visualization.matplotlib.plot_optimization_history(study)
    # fig2 = optuna.visualization.matplotlib.plot_intermediate_values(study)  # That's for pruning
    fig3 = optuna.visualization.matplotlib.plot_parallel_coordinate(study)
    fig4 = optuna.visualization.matplotlib.plot_contour(study)
    fig5 = optuna.visualization.matplotlib.plot_slice(study)
    fig6 = optuna.visualization.matplotlib.plot_param_importances(study)
    fig7 = optuna.visualization.matplotlib.plot_edf(study)
    plt.show()

    # generate data and stop time for this task
    timegan = joblib.load(database_name + '.gz')
    data = cut_data(dataset, objective.seq_len)
    start_time = time.time()
    generated_data = timegan(data, objective.parameters)
    performance.write(str("--- %s minutes ---" % ((time.time() - start_time) / 60)))
    performance.close()
    
    # postprocessing
    fake_data = postprocess_data("eval", generated_data, columns, objective.seq_len, *shift_numbers)

    fake_data.to_csv('fake_data_' + database_name + '.csv', index=False)
    

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()

    parser.add_argument("-num_samples", "--num_samples", type=int, default=500, help="specify number of samples")
    parser.add_argument("-n_trials", "--n_trials", type=int, default=60, help="specify number of optuna trials")
    parser.add_argument("-database_name", "--database_name", type=str, default="timeGAN_default", help="specify the database")
    parser.add_argument("-shift_numbers", "--shift_numbers", nargs='*', type=int, default=(0,), help="specify shifts of the data")
    
    args = parser.parse_args()

    num_samples = args.num_samples
    n_trials = args.n_trials
    database_name = args.database_name
    shift_numbers = args.shift_numbers
    
    run_TimeGAN(num_samples, n_trials, database_name, *shift_numbers)