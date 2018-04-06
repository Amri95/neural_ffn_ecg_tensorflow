from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os, sys
# sys.path.append("..")
import pywt
import pywt.data
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy import signal
import tensorflow as tf

tf.logging.set_verbosity(tf.logging.INFO)


def create_DS(ds_num, v_pre, v_post):
    # ds1_files = ['101','106','108','109','112','114','115','116','118','119','122','124','201','203','205','207','208','209','215','220','223','230']
    ds1_files = ['101']
    # ds2_files = ['100','103','105','111','113','117','121','123','200','202','210','212','213','214','219','221','222','228','231','232','233','234']
    ds2_files = ['100']
    freq = 360
    preX = v_pre
    postX = v_post
    dfall = {} 
    dfann = {} 
    dfseg = {} 
    segment_data = []
    segment_labels = []
    if (ds_num == "1"):
        ds_list = ds1_files;
    else:
        ds_list = ds2_files;
    
    # Load the necessary patient inputs    
    for patient_num in ds_list:
        dfall[patient_num] = pd.read_csv('data/DS' + ds_num + '/' + patient_num + '_ALL_samples.csv', sep=',', header=0, squeeze=False)
        dfann[patient_num] = pd.read_csv('data/DS' + ds_num + '/' + patient_num + '_ALL_ANN.csv', sep=',', header=0, parse_dates=[0], squeeze=False)
   
    # Standardize the beat annotations 
    # vals_to_replace = {'N':'N','L':'N','e':'N','j':'N','R':'N','A':'SVEB','a':'SVEB','J':'SVEB','S':'SVEB','V':'VEB','E':'VEB','F':'F','Q':'Q','P':'Q','f':'Q','U':'Q'}
    # use integers 0..4 instead of annotation...
    vals_to_replace = {'N':0, 'L':0, 'e':0, 'j':0, 'R':0, 'A':1, 'a':1, 'J':1, 'S':1, 'V':2, 'E':2, 'F':3, 'Q':4, 'P':4, 'f':4, 'U':4}
    
    for patient_num in ds_list:
        dfann[patient_num]['Type'] = dfann[patient_num]['Type'].map(vals_to_replace)    
        dfann[patient_num]['RRI'] = (dfann[patient_num]['sample'] - dfann[patient_num]['sample'].shift(1)) / 360
        dfann[patient_num] = dfann[patient_num][1:]  
    
    for patient_num in ds_list:
        annList = [];
        begNList = [];
        endNList = [];
        mixNList = [];
        sliceNList = [];

        for index, row in dfann[patient_num].iterrows():
            Nbegin = row['sample'] - preX;
            Nend = row['sample'] + postX;
            begNList.append(Nbegin);
            endNList.append(Nend);
            annList.append(row['Type'])

        mixNList = tuple(zip(begNList, endNList, annList)) 
        
        for row in mixNList:
            dfseg = dfall[patient_num][(dfall[patient_num]['sample'] >= row[0]) & (dfall[patient_num]['sample'] <= row[1])]
            training_inputs1 = np.asarray(dfseg[dfseg.columns[1:2]].values.flatten(), dtype=np.float32)
            training_inputs2 = np.asarray(dfseg[dfseg.columns[2:3]].values.flatten(), dtype=np.float32)
            segment_data.append(np.concatenate((training_inputs1, training_inputs2), axis=0))
            training_labels = row[2]
            segment_labels.append(training_labels)    
            
    segment_data = np.asarray(segment_data)

    return dfall, dfann, segment_data, segment_labels


def cnn_model_fn(features, labels, mode):
    """Model function for CNN."""
    # Input Layer
    # Reshape X to 4-D tensor: [batch_size, width, height, channels]
    # MNIST images are 28x28 pixels, and have one color channel
    input_layer = tf.reshape(features["x"], [-1, 1, 80, 1])
    
    #print("input_layer: ")
    #print(input_layer.shape)

    # Convolutional Layer #1
    # Computes 32 features using a 5x5 filter with ReLU activation.
    # Padding is added to preserve width and height.
    # Input Tensor Shape: [batch_size, 1, 80, 1]
    # Output Tensor Shape: [batch_size, 1, 78, 5]
    conv1 = tf.layers.conv2d(
        inputs=input_layer,
        filters=5,
        kernel_size=[1, 3],
        # padding="same",
        activation=tf.nn.relu)

    #print("conv1: ")
    #print(conv1.shape)
    
    # Pooling Layer #1
    # First max pooling layer with a 2x2 filter and stride of 2
    # Input Tensor Shape: [batch_size, 1, 78, 5]
    # Output Tensor Shape: [batch_size, 1, 39, 5]
    pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[1, 2], strides=2)

    #print("pool1: ")
    #print(pool1.shape)
    
    # Convolutional Layer #2
    # Computes 64 features using a 5x5 filter.
    # Padding is added to preserve width and height.
    # Input Tensor Shape: [batch_size, 1, 39, 5]
    # Output Tensor Shape: [batch_size, 1, 36, 10]
    conv2 = tf.layers.conv2d(
        inputs=pool1,
        filters=10,
        kernel_size=[1, 4],
        # padding="same",
        activation=tf.nn.relu)

    #print("conv2: ")
    #print(conv2.shape)
    # Pooling Layer #2
    # Second max pooling layer with a 2x2 filter and stride of 2
    # Input Tensor Shape: [batch_size, 1, 36, 10]
    # Output Tensor Shape: [batch_size, 1, 18, 10]

    pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[1, 2], strides=2)

    #print("pool2: ")
    #print(pool2.shape)
    # Flatten tensor into a batch of vectors
    # Input Tensor Shape: [batch_size, 1, 8, 10]
    # Output Tensor Shape: [batch_size, 1, 8, 10]
    pool2_flat = tf.reshape(pool2, [-1, 1 * 18 * 10])

    #print("pool2_flat: ")
    #print(pool2_flat.shape)
    # Dense Layer
    # Densely connected layer with 1024 neurons
    # Input Tensor Shape: [batch_size, 7 * 7 * 64]
    # Output Tensor Shape: [batch_size, 1024]
    dense = tf.layers.dense(inputs=pool2_flat, units=18, activation=tf.nn.relu)

    #print("dense: ")
    #print(dense.shape)
    
    # Add dropout operation; 0.6 probability that element will be kept
    dropout = tf.layers.dropout(
        inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

    #print("dropout: ")
    #print(dropout.shape)
    
    # Logits layer
    # Input Tensor Shape: [batch_size, 1024]
    # Output Tensor Shape: [batch_size, 10]
    logits = tf.layers.dense(inputs=dropout, units=5)
    
    #print("logits: ")
    #print(logits.shape)


    predictions = {
        # Generate predictions (for PREDICT and EVAL mode)
        "classes": tf.argmax(input=logits, axis=1),
        # Add `softmax_tensor` to the graph. It is used for PREDICT and by the
        # `logging_hook`.
        "probabilities": tf.nn.softmax(logits, name="softmax_tensor")
        }
    if mode == tf.estimator.ModeKeys.PREDICT:
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    # Calculate Loss (for both TRAIN and EVAL modes)
    loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)

    # Configure the Training Op (for TRAIN mode)
    if mode == tf.estimator.ModeKeys.TRAIN:
        optimizer = tf.train.GradientDescentOptimizer(learning_rate=0.001)
        train_op = optimizer.minimize(
            loss=loss,
            global_step=tf.train.get_global_step())
        return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

  # Add evaluation metrics (for EVAL mode)
    eval_metric_ops = {
        "accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"])}
    return tf.estimator.EstimatorSpec(
        mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)

