from __future__ import absolute_import, division, print_function, unicode_literals
from preprocessing import prepare_data, regression_f_test, recursive_feature_elim, item_selection, select_sorted_items
from models import univariate_data, create_time_steps, show_plot, multivariate_data, multi_step_plot
import tensorflow as tf
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import json
import csv
import time

def get_predictions():
    # items_predicted = ['Amulet_of_strength', "Green_d'hide_vamb", 'Staff_of_fire', 'Zamorak_monk_top', 'Staff_of_air', \
    #     'Adamantite_bar', 'Zamorak_monk_bottom', 'Adamant_platebody', 'Runite_ore', 'Rune_scimitar', 'Rune_pickaxe', \
    #         'Rune_full_helm', 'Rune_kiteshield', 'Rune_2h_sword', 'Rune_platelegs', 'Rune_platebody', 'Old_school_bond']
    items_predicted = ['Amultet_of_strength']

    data = {}
    names = {}
    count = 0 

    buy_avg = pd.read_csv('data/rsbuddy/buy_average.csv')
    buy_avg = buy_avg.set_index('timestamp')
    buy_avg = buy_avg.drop_duplicates()
    buy_avg = buy_avg.reset_index()
    buy_avg = buy_avg.replace(to_replace=0, method='ffill')

    for item_predicted in items_predicted:
        pass
        df = pd.read_csv('data/predictions/{}.csv'.format(item_predicted))
        current_df = buy_avg[['timestamp', item_predicted]]
        current_df = current_df.rename(columns={'timestamp': 'ts', item_predicted: 'real'})

        merged_df = pd.merge_asof(df, current_df, left_on='timestamp', right_on='ts', direction='backward')
        merged_df = merged_df.tail(48)  # Only show the last 48 time steps (24 hours worth of data)
        chart_data = merged_df.to_dict(orient='records')
        data['{}'.format(count)] = chart_data
        names[count] = item_predicted
        count += 1

    return data, names

def apply_univariate(df, item_to_predict, model, item_std, item_mean, past_history=30):
    
	df_newest_values = df.tail(past_history)[item_to_predict].values
	reshaped_values = np.reshape(df_newest_values, (past_history, 1))
	formatted_values = np.array([reshaped_values])

	#### Unnormalizing the data (so we can see actual prices in GP)
	def unnormalized(val):
		return (val*item_std) + item_mean

	result = unnormalized(model.predict_on_batch(formatted_values)[0])
	
	return result

def apply_multivariate_single_step(df, item_to_predict, model, item_std, item_mean, past_history=30):

	df_newest_values = df.tail(past_history).values
	formatted_values = np.array([df_newest_values])

	#### Unnormalizing the data (so we can see actual prices in GP)
	def unnormalized(val):
		return (val*item_std) + item_mean

	result = unnormalized(model.predict_on_batch(formatted_values)[0])
	
	return result

def apply_multivariate_multi_step(df, item_to_predict, model, item_std, item_mean, future_target=5, past_history=30):
	df_newest_values = df.tail(past_history).values
	formatted_values = np.array([df_newest_values])

	#### Unnormalizing the data (so we can see actual prices in GP)
	def unnormalized(val):
		return (val*item_std) + item_mean

	result = unnormalized(model.predict_on_batch(formatted_values)[0])
	
	return result

labels = ['timestamp', 'uni', 'multiS', 'multiM1', 'multiM2', 'multiM3', 'multiM4', 'multiM5']
def writeToCSV(filename, data, timestamp):
	with open('data/predictions/{}.csv'.format(filename), mode='w', newline='') as GE_data:
		GE_writer = csv.writer(GE_data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
		GE_writer.writerow(labels)  # write field names

		new_array = [timestamp]
		new_array.extend(data)
		GE_writer.writerow(new_array)


def appendToCSV(filename, data, timestamp):
	with open('data/predictions/{}.csv'.format(filename), mode='a', newline='') as GE_data:
		GE_writer = csv.writer(GE_data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

		new_array = [timestamp]
		new_array.extend(data)
		GE_writer.writerow(new_array)    
def run_predictions():
#Get the seconds since epoch
    current_timestamp = int(time.time())
    print("{} - predicting items".format(current_timestamp))

    model_types = ['uni', 'multiS', 'multiM']
	
# SELECT ITEMS
    items_selected = item_selection(drop_percentage=0.5)
    items_to_predict = ['Amulet_of_strength', "Green_d'hide_vamb", 'Staff_of_fire', 'Zamorak_monk_top', 'Staff_of_air', \
 			'Adamantite_bar', 'Zamorak_monk_bottom', 'Adamant_platebody', 'Runite_ore', 'Rune_scimitar', 'Rune_pickaxe', \
 					'Rune_full_helm', 'Rune_kiteshield', 'Rune_2h_sword', 'Rune_platelegs', 'Rune_platebody', 'Old_school_bond']

    preprocessed_df = None
    for item_to_predict in items_to_predict:
        # GET LIST OF FEATURES
        file_name_tail = '03_24_2020'
        if not os.path.isfile('models/features/{}_{}_features.txt'.format(item_to_predict, model_types[0])):
            print ("Model for {} hasn't been created, please run models.py first.".format(item_to_predict))
            return
        specific_feature_list = []
        with open('models/features/{}_{}_features.txt'.format(item_to_predict, model_types[0]), 'r') as filehandle:
            specific_feature_list = json.load(filehandle)

        t0 = time.time()
		# FEATURE EXTRACTION
        preprocessed_df = prepare_data(item_to_predict, items_selected, DATA_FOLDER="data/rsbuddy/", \
			reused_df=preprocessed_df, specific_features=specific_feature_list)

        t1 = time.time()
 		# FEATURE SELECTION & NORMALIZATION
        selected_df, pred_std, pred_mean = regression_f_test(preprocessed_df, item_to_predict, \
 			specific_features=specific_feature_list, number_of_features=len(specific_feature_list)-1)

        t2 = time.time()
        predictions = []
        for model_type in model_types:
 			# LOADING AND APPLYING MODEL
            loaded_model = tf.keras.models.load_model('models/{}_{}_model.h5'.format(item_to_predict, model_type))

            if (model_type == 'uni'):
                result = apply_univariate(selected_df, item_to_predict, loaded_model, pred_std, pred_mean)
            elif (model_type == 'multiS'):
                result = apply_multivariate_single_step(selected_df, item_to_predict, loaded_model, pred_std, pred_mean)
            elif (model_type == 'multiM'):
                result = apply_multivariate_multi_step(selected_df, item_to_predict, loaded_model, pred_std, pred_mean)
            else:
                print("Unrecognized model type.")
			
            predictions.extend(result)
        tf.keras.backend.clear_session()
		
        t3 = time.time()

        print('TIME LOG - preprocessing: {}, feature selection: {}, prediction: {}'.format(t1-t0, t2-t1, t3-t2))

        new_predictions = [int(i) for i in predictions]
        print('item: {}, pred: {}'.format(item_to_predict, new_predictions))
	
        if os.path.isfile('data/predictions/{}_{}.csv'.format(item_to_predict,file_name_tail)):
            appendToCSV(item_to_predict, new_predictions, current_timestamp)
        else:
            writeToCSV(item_to_predict+'_'+file_name_tail, new_predictions, current_timestamp)
    return 