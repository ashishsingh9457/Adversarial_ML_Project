import tensorflow as tf
import matplotlib as mpl
import matplotlib.pyplot as plt
import pickle
import gzip
from objectives import lda_loss
import numpy as np
from keras.datasets import mnist
from keras.optimizers import Adam
from svm import svm_classify
from keras import backend as K

loss_object = lda_loss()

# the path to the final learned features
saved_parameters = './new_features.gz'

# the path to the saved model
model = tf.keras.models.load_model("./model", compile=False)
model.compile(loss=lda_loss(), optimizer=Adam())

# model = tf.keras.models.load_model("./model", custom_objects={'lda_loss': loss_object})

with gzip.open(saved_parameters, 'rb') as fp:
    lda_model_params = pickle.load(fp)

x_train_new = lda_model_params[0][0]
y_train_new = lda_model_params[0][1]

x_test_new = lda_model_params[1][0]
y_test_new = lda_model_params[1][1]


def create_adversarial_pattern(input_image, input_label, epsilon=0.01, alpha=0.02, num_iter=10):
    input_image = tf.convert_to_tensor(input_image, dtype=tf.float32)
    input_label = tf.convert_to_tensor(input_label, dtype=tf.float32)
    
    # Initialize perturbation as zero
    perturbation = tf.zeros_like(input_image)
    
    for i in range(num_iter):
        with tf.GradientTape() as tape:
            tape.watch(input_image)
            prediction = model(input_image + perturbation)
            loss = loss_object(input_label, prediction)
            
        # Get the gradients of the loss w.r.t to the input image.
        gradient = tape.gradient(loss, input_image)

        # Normalize the gradient
        signed_grad = tf.sign(gradient)
        
        # Add the gradient to the perturbation
        perturbation = perturbation + alpha * signed_grad
        
        # Clip the perturbation to epsilon
        perturbation = tf.clip_by_value(perturbation, -epsilon, epsilon)
        
        # Clip the perturbed image to [0, 1]
        adv_x = tf.clip_by_value(input_image + perturbation, 0, 1)
        
    return adv_x - input_image



# Load data
(x_train, y_train), (x_test, y_test) = mnist.load_data()

image_size = x_train.shape[1]
x_train = np.reshape(x_train, [-1, image_size, image_size, 1])
x_test = np.reshape(x_test, [-1, image_size, image_size, 1])

x_train = x_train.astype('float32') / 255
x_test = x_test.astype('float32') / 255

# Get image and its label
# sample = random.sample(range(0, 10000), 10)
# sample = 1  # random.randint(0, 1000)
image = x_test
label = y_test

#perturbations = create_adversarial_pattern(image, label)
# # visualize the perturbations
# plt.imshow(perturbations[0] * 0.5 + 0.5);  # To change [-1, 1] to [0,1]

epsilons = [0, 0.007, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3]
descriptions = [('Epsilon = {:0.3f}'.format(eps) if eps else 'Input')
                for eps in epsilons]

def get_flatten_layer_output(model, x, batch_size=400):
    flatten_layer_output = K.function(
        [model.layers[0].input],  # param 1 will be treated as layer[0].output
        [model.get_layer('flatten').output])  # and this function will return output from flatten layer

    n_sample = x.shape[0]
    n_batch = int((n_sample + batch_size - 1) / batch_size)
    flatten_output = np.empty([n_sample, 10])

    for batch in range(n_batch):
        print(' batch {0}/{1}'.format(batch + 1, n_batch), end='\r')
        start = batch * batch_size
        end = min(n_sample, start + batch_size)
        feature_vector = flatten_layer_output(x[start:end])
        flatten_output[start:end] = feature_vector[0]
    return flatten_output


x_train_new = get_flatten_layer_output(model,x_train)
x_test_new = get_flatten_layer_output(model,x_test)

print('\nEvaluating on original data')
[train_acc, test_acc, pred] = svm_classify(x_train_new, y_train, x_test_new, y_test)
print("Prediction on original data= ", test_acc * 100)

def img_plot(images, epsilon, labels):
    num = images.shape[0]
    num_row = 2
    num_col = 5
    # plot images
    fig, axes = plt.subplots(num_row, num_col, figsize=(1.5 * num_col, 2 * num_row))
    for i in range(num):
        ax = axes[i // num_col, i % num_col]
        ax.imshow(images[i], cmap='gray')
        ax.set_title("Prediction = " + str(labels[i]))
    plt.get_current_fig_manager().set_window_title("PGD_AD (epsilon= " + str(epsilon) + ")")
    plt.tight_layout()
    plt.show()


epsilons = [0, 0.007, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3]
alphas = [0.02] * len(epsilons)
num_iters = [10] * len(epsilons)
descriptions = [('Epsilon = {:0.3f}'.format(eps) if eps else 'Input')
                for eps in epsilons]

for i, eps in enumerate(epsilons):
    adv_x = create_adversarial_pattern(image, label, epsilon=eps, alpha=alphas[i], num_iter=num_iters[i])
    adv_x = tf.clip_by_value(image + adv_x, 0, 1)
    adv_x_new = get_flatten_layer_output(adv_x)
    [train_acc, test_acc, pred] = svm_classify(x_train_new, y_train, adv_x_new, y_test)
    print("New prediction on eps="+str(eps)+" : ", test_acc*100)
    img_plot(adv_x[:10], eps, pred)
