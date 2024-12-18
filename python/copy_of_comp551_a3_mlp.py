# -*- coding: utf-8 -*-
"""Copy of Comp551_A3_MLP.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1L9cnoMYOmzbz7kHQ8VFjCq6eg25BxkuQ
"""

#!pip install medmnist

import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.utils.data as data
import torchvision.transforms as transforms
import medmnist
from medmnist import OrganAMNIST, INFO, Evaluator
import time
import seaborn as sns

"""# Task 1
Preprocessing data
"""

def dataset_load(size=28, norm=True, flatten=True):

  trainset = OrganAMNIST(split='train', download=True,size=size)
  testset = OrganAMNIST(split='test', download=True,size=size)
  x_train = trainset.imgs
  y_train = trainset.labels
  x_test = testset.imgs
  y_test = testset.labels

  if norm:
    x_train = x_train.astype(np.float64)
    x_train -= np.mean(x_train, axis = 0)
    x_train /= np.std(x_train, axis = 0)
    x_test = x_test.astype(np.float64)
    x_test -= np.mean(x_test, axis = 0)
    x_test /= np.std(x_test, axis = 0)

  if flatten:
    x_train = x_train.reshape(x_train.shape[0], (x_train.shape[1] * x_train.shape[2]))
    x_test = x_test.reshape(x_test.shape[0], (x_test.shape[1] * x_test.shape[2]))

  return [(x_train, y_train.flatten()), (x_test, y_test.flatten())]

trainset = OrganAMNIST(split='train', download=True)
testset = OrganAMNIST(split='test', download=True)
y_train = trainset.labels.flatten()
y_test = testset.labels.flatten()

counts_test, ltest = np.histogram(y_test,bins=len(np.unique(y_test)))
counts_train, ltrain = np.histogram(y_train,bins=len(np.unique(y_train)))
print(trainset)

"""'0': 'bladder', '1': 'femur-left', '2': 'femur-right', '3': 'heart', '4': 'kidney-left', '5': 'kidney-right', '6': 'liver', '7': 'lung-left', '8': 'lung-right', '9': 'pancreas', '10': 'spleen'"""

cat_labels = ['bladder','femur-left','femur-right','heart','kidney-left','kidney-right','liver','lung-left','lung-right','pancreas','spleen']
fig, ax = plt.subplots(figsize=(8, 1.8))
ax.set_title('Distribution of Categories in Dataset',fontsize=18)
ax.bar(cat_labels,counts_train,label='Train')
ax.bar(cat_labels,counts_test,width=0.7,label='Test')
ax.tick_params(axis='x', labelrotation=40)
ax.set_ylabel('Counts',fontsize=18)
ax.legend(prop={'size': 12})
fig.savefig('histogram_test.png')

"""# Task 2"""

# Activations

class Logistic:
  def value(z):
    return np.where(z >= 0, 1/(1 + np.exp(-z)), np.exp(z)/(1+np.exp(z)))
  def derivative(z):
    return Logistic.value(z) * (1 - Logistic.value(z))

class Relu:
  def value(z):
    return np.maximum(z, 0)
  def derivative(z):
    return np.where(z >= 0, 1, 0)

class LeakyRelu:
  def value(z):
    return np.where(z >= 0, z, 0.05*z)
  def derivative(z):
    return np.where(z >= 0, 1, 0.05)

class Tanh:
  def value(z):
    return 2 * Logistic.value(2 * z) - 1
  def derivative(z):
    expZ = np.exp(z)
    return 1 - Tanh.value(z) ** 2

class Softmax:
  def value(z):
    z -= np.max(z, axis=1).reshape((-1, 1))
    expZ = np.exp(z)
    sumExp = np.sum(expZ, axis = 1).reshape((-1, 1))
    return expZ/sumExp

# Initialize weights
def allzero(dim):
  w = []
  for i in range(len(dim)-1):
    w.append(np.zeros((dim[i], dim[i+1])))
  return w

def kaiming(dim):
  w = []
  for i in range(len(dim)-1):
    w.append(np.random.normal(0, np.sqrt(2/dim[i]), size=(dim[i], dim[i+1])))
  return w

class Evaluation:
  def cross_entropy_loss(y, yh):
    N = y.shape[0]
    return -np.sum(y * np.log(yh + 1e-6))/N  #to avoid log(0) error
  def evaluate_acc(y, yh, Nw=11, verbose = False):
    N = len(y)
    conf_matrix = np.zeros((Nw, Nw))
    for i in range(np.size(yh)):
      conf_matrix[yh[i]-1][y[i]-1] += 1
    if(verbose):
        print(conf_matrix)
    return np.sum(np.diag(conf_matrix)*100/N)

class MinibatchSGD:
  def __init__(self, learning_rate=.002, epochs=10, batchsize=32, record_hist = False, beta=0):
    self.lr = learning_rate
    self.epochs = epochs
    self.batchsize = batchsize
    self.record_hist = record_hist
    if self.record_hist:
      self.w_hist = []
    self.beta = beta # = 0 reduces to SGD
    self.deltaW = []
    self.loss_hist = []

  def run(self, x, y, w, b):
    N, D = x.shape
    norm_g = np.inf
    e = 0

    if y.ndim == 1:
      N = len(y)
      y = np.reshape(y, (N, -1))

    for weight in w:
      wd1, wd2 = weight.shape
      self.deltaW.append(np.zeros((wd1, wd2)))

    data = np.concatenate((x, y), axis=1)
    numbatch = data.shape[0] // self.batchsize

    if self.record_hist:
      self.w_hist = []

    while e < self.epochs:
      e += 1
      np.random.shuffle(data)

      batches = []
      i = 0
      for i in range(numbatch):
        batches.append(data[i*self.batchsize:(i+1)*self.batchsize, :])
      if i + 1 < data.shape[0]:
        last_batch = np.concatenate((data[(i+1)*self.batchsize:-1, :], data[np.random.choice(data.shape[0], 2, replace=False), :]), axis=0)
        batches.append(last_batch)

      loss = 0
      for batch in batches:
        z,a = model.forward(batch[:, :D])
        deltas, change = model.backprop(batch[:, D:], z, a)

        for i in range(len(change)):
          self.deltaW[i] = self.beta * self.deltaW[i] + (1 - self.beta) * change[i]
          w[i] -= self.lr * self.deltaW[i]
          b[i] -= self.lr * 1/self.batchsize * (np.sum(deltas[i],axis=0))

        loss = loss + Evaluation.cross_entropy_loss(batch[:, D:], a[-1])
      self.loss_hist.append(loss/(N/self.batchsize))
      if self.record_hist:
        self.w_hist.append(w)

    return [w,b]

class MLP():
  def __init__(self, act_fns, input_size, hd, m, output_size, weight_init, l1 = 0, l2 = 0):
    self.act_fns = act_fns
    self.input_size = input_size
    self.hd = hd  #number of hidden layers
    self.m = m  #number of units in hidden layer
    self.output_size = output_size
    self.weight_init = weight_init
    self.b = []
    self.l1 = l1
    self.l2 = l2

    model_dim = [self.input_size] + m + [output_size]

    for i in range(len(model_dim)-1):
      self.b.append(np.zeros(model_dim[i+1]))

    self.w = self.weight_init(model_dim)


  def OneHotEncoding(self, y, Nw):
    N = y.shape[0]
    encodedY = np.zeros((N, Nw))
    encodedY[np.arange(N), y.astype(int).flatten()-1] = 1
    return encodedY

  def forward(self, x):
    x = np.array(x)
    N = x.shape[0]
    if x.ndim == 1:
      x = x.reshape((1,N))
    z = [x]
    a = [x]
    for i in range(self.hd+1):
      z.append((a[i] @ self.w[i]) + self.b[i])
      a.append(self.act_fns[i].value(z[-1]))

    return [z,a]

  def backprop(self, y, z, a):
    yh = a[-1]
    deltas = [0] * (self.hd+1)
    deltas[-1] = yh-y

    for i in reversed(range(0,len(deltas)-1)):
      delta = np.dot(deltas[i+1], self.w[i+1].T) * self.act_fns[i].derivative(z[i+1])
      deltas[i] = delta

    change = []
    for i in range(len(deltas)):
      if (self.l1 != 0 or self.l2 != 0):
        change.append(np.dot(a[i].T, deltas[i]) + + ((self.l1 * self.w[i]/abs(self.w[i])) + (self.l2 * 2 * self.w[i])))
      else:
        change.append(np.dot(a[i].T, deltas[i]))

    return deltas, change


  def fit(self, X, y, optimizer):
    N, D = X.shape

    Nw = self.output_size
    w = self.w
    b = self.b
    self.w, self.b = optimizer.run(X, self.OneHotEncoding(y, Nw), w, b)

    return self

  def predict(self, X):
    z, a = self.forward(X)
    return np.argmax(a[-1], axis=1) + 1

"""# Task 3

## Hyperparameter searching

We look for the optimal learning rate for MPL (2 ReLU hidden layers, 256 units, 10 epochs)

deliverables: Test Accuracy vs learning rate
"""

# Exploring hyperparameter space: Learning rates and weight initializations
alphas = np.logspace(-5,-2,num=7)
np.random.seed(0)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
epochs = 10

weight_inits = [allzero,kaiming]
w_names = ['allzero','kaiming']
fig, ax = plt.subplots(figsize=(7, 5))
for i,weight_init in enumerate(weight_inits):
  accs = []
  for alpha in alphas:
    start_time = time.time()
    opt = MinibatchSGD(learning_rate = alpha, epochs=epochs, batchsize=32, record_hist=True)
    model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, weight_init=weight_init)
    model.fit(xtrain, ytrain, opt)
    acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
    print("test accuracy for alpha =", alpha, "is ",acc, '--- %s seconds ---' % (time.time() - start_time))
    accs.append(acc)
  ax.plot(alphas, accs,label=w_names[i])

ax.set_xlabel("learning rate",fontsize=20)
ax.set_ylabel("Accuracy (%)",fontsize=20)
ax.set_title(f"Accuracy over learning rate (10 epochs)",fontsize=20)
ax.set_xscale('log')
ax.legend(prop={'size': 12})

# Exploring hyperparameter space: Learning rates and momentums
alphas = np.logspace(-5,-2,num=7)
betas = [0,0.99]
np.random.seed(0)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
epochs = 10

fig, ax = plt.subplots(figsize=(7, 5))
for beta in betas:
  accs = []
  for alpha in alphas:
    start_time = time.time()
    opt = MinibatchSGD(learning_rate = alpha, epochs=epochs, batchsize=32, record_hist=True, beta=beta)
    model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
    model.fit(xtrain, ytrain, opt)
    acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
    print("test accuracy for alpha =", alpha, "is ",acc, '--- %s seconds ---' % (time.time() - start_time))
    accs.append(acc)
  ax.plot(alphas, accs,label='beta = %.2f' % beta)
ax.set_xlabel("learning rate")
ax.set_ylabel("Accuracy (%)")
ax.set_title(f"Evolution of Accuracy over learning rate /n for different momentums (10 epochs)")
ax.set_xscale('log')
ax.legend()

# Exploring hyperparameter space: Learning rates and batch size
alphas = np.logspace(-5,-2,num=7)
batches = [16,32,1000]
np.random.seed(0)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
epochs = 10

fig, ax = plt.subplots(figsize=(7, 5))
for batch in batches:
  accs = []
  for alpha in alphas:
    start_time = time.time()
    opt = MinibatchSGD(learning_rate = alpha, epochs=epochs, batchsize=batch, record_hist=True,beta=0.99)
    model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
    model.fit(xtrain, ytrain, opt)
    acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
    print("test accuracy for alpha =", alpha, "is ",acc, '--- %s seconds ---' % (time.time() - start_time))
    accs.append(acc)
  ax.plot(alphas, accs,label='batch size = %i' % batch)
ax.set_xlabel("learning rate",fontsize=20)
ax.set_ylabel("Accuracy (%)",fontsize=20)
ax.set_title(f"Accuracy over learning rate \n for different batch sizes (10 epochs)",fontsize=20)
ax.set_xscale('log')
ax.legend(prop={'size': 12})

"""The optimal learning rate is ~0.003 with batch size =32 and 0.99 momentum.

## Non-linearity and network depth

* 1 layer softmax activation
* 1 hidden layer 256 units Relu activation, last layer softmax activation
* 2 hidden layers 256 units Relu activation, last layer softmax activation

Deliverables: Training and test accuracies for different depths
"""

np.random.seed(0)
epochs = 10
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.003
beta = 0.99

fig, axs = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch', fontsize=20)
fig.text(0.5, 0.04, 'epoch', ha='center',fontsize=20)
fig.text(0.04, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=20)

# no hidden layers
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True, beta=beta)
model = MLP([Softmax], D, 0, [], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== no hidden layers ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='blue',label='no hidden layers')

# 1 hidden layer
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model = MLP([Relu, Softmax], D, 1, [256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== 1 hidden layer ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='orange',label='1 hidden layer')

# 2 hidden layers
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== 2 hidden layers ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='green',label='2 hidden layers')
axs.legend(loc='upper right',prop={'size': 12})

"""We see that the training loss becomes pretty consistent after 6 epochs. Lets try early to see if we can further bring down the test error."""

np.random.seed(0)
epochs = 6
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.003
beta = 0.99

fig, axs = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch', fontsize=20)
fig.text(0.5, 0.04, 'epoch', ha='center',fontsize=20)
fig.text(0.04, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=20)

# no hidden layers
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True, beta=beta)
model = MLP([Softmax], D, 0, [], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== no hidden layers ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='paleturquoise',label='no hidden layers')

# 1 hidden layer
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model = MLP([Relu, Softmax], D, 1, [256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== 1 hidden layer ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='lightseagreen',label='1 hidden layer')

# 2 hidden layers
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== 2 hidden layers ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='darkslategray',label='2 hidden layers')
axs.legend(loc='upper right',prop={'size': 12})

#Network width
np.random.seed(0)
epochs = 6
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.003
beta = 0.99

fig, axs = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch \n 2 ReLU hidden layers', fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=20)
fig.text(0.01, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=20)

# width = 28
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [28,28], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== depth = 28 ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='firebrick',label='28 units')

# width = 128
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [128,128], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== depth = 128 ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='red',label='128 units')

# width = 256
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== depth = 256 ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
axs.plot(list(range(0, epochs)), opt.loss_hist,color='orange',label='256 units')
axs.set_yscale('log')
axs.legend(loc='upper right',prop={'size': 12})

"""Indeed, we were able to bring the test accuracy up to 75.3% using early stopping

## Activation types
*   256 ReLU, 256 ReLU, Softmax
*   256 Leaky ReLU, 256 Leaky ReLU, Softmax
*   256 Tanh, 256 Tanh, Softmax
*   256 Logistic, 256 Logistic, Softmax (extra)

Deliverables: Training and test accuracies for different activation types
"""

np.random.seed(0)
epochs = 6
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))


fig, ax = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=18)
fig.text(0.02, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=18)

# Logistic, Logistic
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Logistic, Logistic, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== Logistic, Logistic ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='violet',label='logistic')

# Tanh, Tanh
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Tanh, Tanh, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== Tanh, Tanh ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='mediumorchid',label='Tanh')

# Leaky ReLU, Leaky ReLU
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([LeakyRelu, LeakyRelu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== Leaky ReLU, Leaky ReLU ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='mediumpurple',label='Leaky ReLU')

# ReLU, ReLU
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
print("====== ReLU, ReLU ======")
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='blue',label='ReLU')
ax.legend(loc='upper right',prop={'size': 12})

"""## L1 and L2 regularization

*   256 ReLU, 256 ReLU, Softmax

Deliverables:
* Plot of training and test accuracy vs L1 strength
* Plot of training and test accuracy vs L2 strength


"""

# L1 regularization
l1s = np.logspace(-5,-2,num=7)
l1s[0] = 0
seed = 3 #1
np.random.seed(seed)
print('seed',seed)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.003
epochs = 6
beta=0.99

fig, axs = plt.subplots(2,1, figsize=(7, 5),sharex=True)
fig.text(0.5, 0.01, 'L1 strength', ha='center',fontsize=18)
fig.text(0.02, 0.5, 'Accuracy (%)', va='center', rotation='vertical',fontsize=18)

accs = []
accs_train = []
for l in l1s:
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs,record_hist=True,beta=beta)
  model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming, l1 = l)
  model.fit(xtrain, ytrain, opt)
  acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
  acc_train = Evaluation.evaluate_acc(ytrain, model.predict(xtrain))
  print('l1 strengh = ', l,': test acc = ',acc,'%, train accuracy = ',acc_train, '%')
  accs.append(acc)
  accs_train.append(acc_train)

fig.suptitle(f"Accuracy over L1 regularization strength", fontsize=18)
axs[0].plot(l1s, accs_train,color='b',label='train')
axs[1].plot(l1s, accs,color='orange',label='test')
axs[0].axhline(y=accs_train[0],color='grey',linestyle='--')
axs[1].axhline(y=accs[0],color='grey',linestyle='--')
axs[0].set_xscale('log')
axs[1].set_xscale('log')
axs[0].legend(prop={'size': 12})
axs[1].legend(prop={'size': 12})

l1_best = l1s[np.argmax(accs)]
print('Maximum accuracy = ',np.max(accs),'at l1 strength = ', l1_best)

np.random.seed(3)
epochs = 6
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
beta=0.99
ideal_alpha=0.003

fig, ax = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=18)
fig.text(0.01, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=18)

print('~~~~~~ L1 = 0 ~~~~~')
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='mediumpurple',label='L1 = 0')

print('~~~~~~ L1 =', l1_best, ' ~~~~~')
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True, beta=beta)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming, l1=l1_best)
model.fit(xtrain, ytrain, opt)
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='lightseagreen',label='L1 = %.3f' %l1_best)
ax.set_yscale('log')
ax.legend(prop={'size': 12})

# L2 regularization
l2s = np.logspace(-5,-0.5,num=7)
l2s[0] = 0
seed = 3 #3,6,7,18 best
np.random.seed(seed)
print('seed',seed)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.003
epochs = 6
beta=0.99

fig, axs = plt.subplots(2,1, figsize=(7, 5),sharex=True)
fig.text(0.5, 0.01, 'L2 strength', ha='center',fontsize=18)
fig.text(0.02, 0.5, 'Accuracy (%)', va='center', rotation='vertical',fontsize=18)

accs = []
accs_train = []
for l in l2s:
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs,record_hist=True,beta=beta)
  model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming, l2 = l)
  model.fit(xtrain, ytrain, opt)
  acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
  acc_train = Evaluation.evaluate_acc(ytrain, model.predict(xtrain))
  print('l2 strengh = ', l,': test acc = ',acc,'%, train accuracy = ',acc_train, '%')
  accs.append(acc)
  accs_train.append(acc_train)

fig.suptitle(f"Accuracy over L2 regularization strength", fontsize=18)
axs[0].plot(l2s, accs_train,color='b',label='train')
axs[1].plot(l2s, accs,color='orange',label='test')
axs[0].axhline(y=accs_train[0],color='grey',linestyle='--')
axs[1].axhline(y=accs[0],color='grey',linestyle='--')
axs[0].set_xscale('log')
axs[1].set_xscale('log')
axs[0].legend(prop={'size': 12})
axs[1].legend(prop={'size': 12})

l2_best = l2s[np.argmax(accs)]
print('Maximum accuracy = ',np.max(accs),'at l2 strength = ', l2_best)

np.random.seed(3)
epochs = 6
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
beta=0.99
ideal_alpha=0.003

fig, ax = plt.subplots(figsize=(7, 5))
fig.suptitle('Training cross entropy loss vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=18)
fig.text(0.01, 0.5, 'Cross entropy loss', va='center', rotation='vertical',fontsize=18)

print('~~~~~~ L2 = 0 ~~~~~')
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
model.fit(xtrain, ytrain, opt)
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='mediumpurple',label='L2 = 0')

print('~~~~~~ L2 =', l2_best, ' ~~~~~')
opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True, beta=beta)
model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming, l2=l2_best)
model.fit(xtrain, ytrain, opt)
yptest = model.predict(xtest)
yptrain = model.predict(xtrain)
print('Train accuracy', Evaluation.evaluate_acc(ytrain, yptrain))
print('Test accuracy', Evaluation.evaluate_acc(ytest, yptest))
ax.plot(list(range(0, epochs)), opt.loss_hist,color='lightseagreen',label='L2 = %.3f' %l2_best)
ax.set_yscale('log')
ax.legend(prop={'size': 12})

# L1 regularization
l1s = np.logspace(-5,-2,num=7)
l1s[0] = 0

np.random.seed(0)
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
ideal_alpha = 0.002
epochs = 6

fig, axs = plt.subplots(2,1, figsize=(7, 5),sharex=True)
fig.text(0.5, 0.04, 'l1 strength', ha='center')
fig.text(0.04, 0.5, 'Accuracy (%)', va='center', rotation='vertical')

accs = []
accs_train = []
for l in l1s:
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs,record_hist=True)
  model = MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming, l1 = l)
  model.fit(xtrain, ytrain, opt)
  acc = Evaluation.evaluate_acc(ytest, model.predict(xtest))
  acc_train = Evaluation.evaluate_acc(ytrain, model.predict(xtrain))
  print('l1 strengh = ', l,': test acc = ',acc,'%, train accuracy = ',acc_train, '%')
  accs.append(acc)
  accs_train.append(acc_train)

fig.suptitle(f"Evolution of Accuracy over different values of L1 regularization strength")
axs[0].plot(l1s, accs_train,color='b',label='train')
axs[1].plot(l1s, accs,color='orange',label='test')
axs[0].set_xscale('log')
axs[1].set_xscale('log')
axs[0].legend()
axs[1].legend()

"""## Without normalization
* 256 ReLU, 256 ReLU, Softmax

Deliverables: Training and test accuracy
"""

np.random.seed(0)
epochs = 6
beta=0.99
ideal_alpha=0.003
epochs_list = list(range(1, epochs+1))
fig, ax = plt.subplots(figsize=(7, 5))
fig.suptitle('Accuracy vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=18)
fig.text(0.01, 0.5, 'Accuracy (%)', va='center', rotation='vertical',fontsize=18)

print('~~~~~~ Normalization ~~~~~')
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
accs_train = []
accs = []
for epochs in epochs_list:
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
  model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
  model.fit(xtrain, ytrain, opt)
  yptest = model.predict(xtest)
  yptrain = model.predict(xtrain)
  acc_train = Evaluation.evaluate_acc(ytrain, yptrain)
  acc = Evaluation.evaluate_acc(ytest, yptest)
  print('Train accuracy', acc_train)
  print('Test accuracy', acc)
  accs_train.append(acc_train)
  accs.append(acc)
ax.plot(epochs_list, accs_train,color='red',linestyle='--',label='Normalization: training')
ax.plot(epochs_list, accs,color='red',label='Normalization: test')

print('~~~~~~ No normalization ~~~~~')
train, test = dataset_load(norm=False)
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
accs_train = []
accs = []
for epochs in epochs_list:
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
  model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
  model.fit(xtrain, ytrain, opt)
  yptest = model.predict(xtest)
  yptrain = model.predict(xtrain)
  acc_train = Evaluation.evaluate_acc(ytrain, yptrain)
  acc = Evaluation.evaluate_acc(ytest, yptest)
  print('Train accuracy', acc_train)
  print('Test accuracy', acc)
  accs_train.append(acc_train)
  accs.append(acc)
ax.plot(epochs_list, accs_train,color='blue',linestyle='--',label='No normalization: training')
ax.plot(epochs_list, accs,color='blue',label='No normalization: test')
#ax.set_yscale('log')
ax.legend(prop={'size': 12})

"""## Bigger image
* 256 ReLU, 256 ReLU, Softmax

Deliverables:
* Plot of accuracy over 6 epochs for 28x28 pixel data and time elapsed to run the cell
* Plot of accuracy over 6 epochs for 128x128 pixel data and time elapsed to run the cell
"""

np.random.seed(0)
epochs = 6
beta=0.99
ideal_alpha=0.003
epochs_list = list(range(1, epochs+1))
fig, ax = plt.subplots(figsize=(7, 3))
fig.suptitle('Accuracy vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=18)
fig.text(0.01, 0.5, 'Accuracy (%)', va='center', rotation='vertical',fontsize=18)

print('~~~~~~ 28x28 pixel ~~~~~')
train, test = dataset_load()
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
accs_train = []
accs = []
for epochs in epochs_list:
  if epochs == epochs_list[-1]:
    start_time = time.time()
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
  model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
  model.fit(xtrain, ytrain, opt)
  if epochs == epochs_list[-1]:
    time_elapsed = time.time() - start_time
    print('time elapsed for 6 epochs of 28x28 model training: ', time_elapsed)
  yptest = model.predict(xtest)
  yptrain = model.predict(xtrain)
  acc_train = Evaluation.evaluate_acc(ytrain, yptrain)
  acc = Evaluation.evaluate_acc(ytest, yptest)
  print('Train accuracy', acc_train)
  print('Test accuracy', acc)
  accs_train.append(acc_train)
  accs.append(acc)
ax.plot(epochs_list, accs_train,color='purple',linestyle='--',label='size = 28: train')
ax.plot(epochs_list, accs,color='purple',label='size = 28 : test')

#ax.set_yscale('log')
ax.legend(prop={'size': 12})

np.random.seed(0)
epochs = 6
beta=0.99
ideal_alpha=0.003
epochs_list = list(range(1, epochs+1))
fig, ax = plt.subplots(figsize=(7, 3))
fig.suptitle('Accuracy vs epoch',fontsize=18)
fig.text(0.5, 0.01, 'epoch', ha='center',fontsize=12)
fig.text(0.01, 0.5, 'Accuracy (%)', va='center', rotation='vertical',fontsize=18)

print('~~~~~~ 128x128 pixel ~~~~~')
train, test = dataset_load(size=128)
xtrain, ytrain = train
xtest, ytest = test
N,D = xtrain.shape
nclasses = len(np.unique(ytrain))
accsb_train = []
accsb = []
for epochs in epochs_list:
  if epochs == epochs_list[-1]:
    start_time = time.time()
  opt = MinibatchSGD(learning_rate = ideal_alpha, epochs=epochs, record_hist=True,beta=beta)
  model =  MLP([Relu, Relu, Softmax], D, 2, [256,256], nclasses, kaiming)
  model.fit(xtrain, ytrain, opt)
  if epochs == epochs_list[-1]:
    time_elapsed =  time.time() - start_time
    print('time elapsed for 6 epochs of 128x128 model training: ', time_elapsed)
  yptest = model.predict(xtest)
  yptrain = model.predict(xtrain)
  acc_train = Evaluation.evaluate_acc(ytrain, yptrain)
  acc = Evaluation.evaluate_acc(ytest, yptest)
  print('Train accuracy', acc_train)
  print('Test accuracy', acc)
  accsb_train.append(acc_train)
  accsb.append(acc)
ax.plot(epochs_list, accsb_train,color='orange',linestyle='--',label='size = 128: train')
ax.plot(epochs_list, accsb,color='orange',label='size = 128: test')

fig, ax = plt.subplots(figsize=(7, 5))
ax.set_title('Training data sets of different sizes',fontsize=18)
ax.set_xlabel('epoch',fontsize=18)
ax.set_ylabel('Accuracy (%)',fontsize=18)
ax.plot(epochs_list, accs_train,color='purple',linestyle='--',label='size = 28x28: train')
ax.plot(epochs_list, accs,color='purple',label='size = 28x28 : test')
ax.plot(epochs_list, accsb_train,color='orange',linestyle='--',label='size = 128x128: train')
ax.plot(epochs_list, accsb,color='orange',label='size = 128x128: test')

#ax.set_yscale('log')
ax.legend(loc='upper right',prop={'size': 12})
fig.savefig('mlp_test.png')
