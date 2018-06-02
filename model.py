#!/usr/bin/python3
# -*- coding: utf-8 -*-

# library modules
import json
import time
import os

# External library modules
import tensorflow as tf
import numpy as np

# local modules
from data import LSVRC2010
import logs

class AlexNet:
    """
    A tensorflow implementation of the paper:
    `AlexNet <https://papers.nips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks.pdf>`_
    """

    def __init__(self, path):
        """
        Build the AlexNet model
        """
        self.logger = logs.get_logger()

        self.path = path
        self.lsvrc2010 = LSVRC2010(self.path)
        self.num_classes = len(self.lsvrc2010.folders)

        self.learning_rate = 0.01
        self.input_shape = (None, 227, 227, 3)
        self.output_shape = (128, 200)

        self.logger.info("Creating placeholders for graph...")
        self.create_tf_placeholders()

        self.logger.info("Initialize hyper parameters...")
        self.hyper_param = {}
        self.init_hyper_param()

    def create_tf_placeholders(self):
        """
        Create placeholders for the graph.
        The input for these will be given while training or testing.
        """
        self.input_image = tf.placeholder(tf.float32, shape=self.input_shape,
                                          name='input_image')
        self.labels = tf.placeholder(tf.int32, shape=self.output_shape,
                                     name='output')

    def init_hyper_param(self):
        """
        Store the hyper parameters.
        For each layer store number of filters(kernels)
        and filter size.
        If it's a fully connected layer then store the number of neurons.
        """
        with open('hparam.json') as f:
            self.hyper_param = json.load(f)

    def get_filter(self, layer_num, layer_name):
        """
        :param layer_num: Indicates the layer number in the graph
        :type layer_num: int
        :param layer_name: Name of the filter
        """
        layer = 'L' + str(layer_num)

        filter_height, filter_width, in_channels = self.hyper_param[layer]['filter_size']
        out_channels = self.hyper_param[layer]['filters']

        return tf.Variable(tf.truncated_normal(
            [filter_height, filter_width, in_channels, out_channels],
            dtype = tf.float32, stddev = 1e-1), name = layer_name)

    def get_strides(self, layer_num):
        """
        :param layer_num: Indicates the layer number in the graph
        :type layer_num: int
        """
        layer = 'L' + str(layer_num)

        stride = self.hyper_param[layer]['stride']
        strides = [1, stride, stride, 1]

        return strides

    def build_graph(self):
        """
        Build the tensorflow graph for AlexNet.

        First 5 layers are Convolutional layers. Out of which
        first 2 and last layer will be followed by *max pooling*
        layers.

        Next 2 layers are fully connected layers.

        L1_conv -> L1_MP -> L2_conv -> L2_MP -> L3_conv
        -> L4_conv -> L5_conv -> L5_MP -> L6_FC -> L7_FC

        Where L1_conv -> Convolutional layer 1
              L5_MP -> Max pooling layer 5
              L7_FC -> Fully Connected layer 7

        Use `tf.nn.conv2d` to initialize the filters so
        as to reduce training time and `tf.layers.max_pooling2d`
        as we don't need to initialize in the pooling layer.
        """
        # Layer 1 Convolutional layer
        filter1 = self.get_filter(1, 'L1_filter')
        l1_conv = tf.nn.conv2d(self.input_image, filter1,
                               self.get_strides(1),
                               padding = self.hyper_param['L1']['padding'],
                               name='L1_conv')

        # Layer 1 Max Pooling layer
        l1_MP = tf.layers.max_pooling2d(l1_conv,
                                        self.hyper_param['L1_MP']['filter_size'],
                                        self.hyper_param['L1_MP']['stride'],
                                        name='L1_MP')

        # Layer 2 Convolutional layer
        filter2 = self.get_filter(2, 'L2_filter')
        l2_conv = tf.nn.conv2d(l1_MP, filter2,
                               self.get_strides(2),
                               padding = self.hyper_param['L2']['padding'],
                               name='L2_conv')

        # Layer 2 Max Pooling layer
        l2_MP = tf.layers.max_pooling2d(l2_conv,
                                        self.hyper_param['L2_MP']['filter_size'],
                                        self.hyper_param['L2_MP']['stride'],
                                        name='L2_MP')

        # Layer 3 Convolutional layer
        filter3 = self.get_filter(3, 'L3_filter')
        l3_conv = tf.nn.conv2d(l2_MP, filter3,
                               self.get_strides(3),
                               padding = self.hyper_param['L3']['padding'],
                               name='L3_conv')

        # Layer 4 Convolutional layer
        filter4 = self.get_filter(4, 'L4_filter')
        l4_conv = tf.nn.conv2d(l3_conv, filter4,
                               self.get_strides(4),
                               padding = self.hyper_param['L4']['padding'],
                               name='L4_conv')

        # Layer 5 Convolutional layer
        filter5 = self.get_filter(5, 'L5_filter')
        l5_conv = tf.nn.conv2d(l4_conv, filter5,
                               self.get_strides(5),
                               padding = self.hyper_param['L5']['padding'],
                               name='L5_conv')

        # Layer 5 Max Pooling layer
        l5_MP = tf.layers.max_pooling2d(l5_conv,
                                        self.hyper_param['L5_MP']['filter_size'],
                                        self.hyper_param['L5_MP']['stride'],
                                        name='L5_MP')

        flatten = tf.layers.flatten(l5_MP)

        # Layer 6 Fully connected layer
        l6_FC = tf.contrib.layers.fully_connected(flatten,
                                                  self.hyper_param['FC6'])

        # Layer 7 Fully connected layer
        l7_FC = tf.contrib.layers.fully_connected(flatten,
                                                  self.hyper_param['FC7'])

        # final layer before softmax
        self.logits = tf.contrib.layers.fully_connected(l7_FC,
                                                        self.num_classes)

        # loss function
        loss_function = tf.nn.softmax_cross_entropy_with_logits(
            logits = self.logits,
            labels = self.labels
        )

        # total loss
        self.loss = tf.reduce_mean(loss_function)

        self.optimizer = tf.train.AdamOptimizer(self.learning_rate).minimize(self.loss)

        correct = tf.equal(tf.argmax(self.logits, 1), tf.argmax(self.labels, 1))
        self.accuracy = tf.reduce_mean(tf.cast(correct, tf.float32))

    def train(self, batch_size, epochs):
        """
        Train AlexNet.
        """
        batches = self.lsvrc2010.get_images_for_1_batch(batch_size,
                                                        self.input_shape[1:3])

        self.logger.info("Building the graph...")
        self.build_graph()

        init = tf.global_variables_initializer()

        saver = tf.train.Saver()
        with tf.Session() as sess:
            sess.run(init)

            losses = []
            best_loss = float('inf')
            accuracies = []
            for epoch in range(epochs):
                for batch_i, cur_batch in enumerate(batches):
                    start = time.time()
                    _, loss, acc = sess.run([self.optimizer, self.loss, self.accuracy],
                                            feed_dict = {
                                                self.input_image: cur_batch[0],
                                                self.labels: cur_batch[1]
                                            })
                    end = time.time()

                    losses.append(loss)
                    accuracies.append(acc)
                    self.logger.info("Time: %f Epoch: %d Batch: %d Loss: %f Accuracy: %f",
                                     end - start, epoch, batch_i,
                                     sum(losses) / len(losses),
                                     sum(accuracies) / len(accuracies))

                cur_loss = sum(losses) / len(losses)
                if cur_loss < best_loss:
                    model_base_path = os.path.join(os.getcwd(), 'model')
                    if not os.path.exists(model_base_path):
                        os.mkdir(model_base_path)
                    model_save_path = os.path.join(os.getcwd(), 'model', 'model.ckpt')
                    save_path = saver.save(sess, model_save_path)
                    self.logger.info("Batch %d Model saved in path: %s", epoch, save_path)

    def test(self):
        raise NotImplementedError

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('image_path', metavar = 'image-path',
                        help = 'ImageNet dataset path')
    args = parser.parse_args()

    alexnet = AlexNet(args.image_path)
    alexnet.train(128, 100)
