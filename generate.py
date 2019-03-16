import tensorflow as tf
import numpy as np
import skimage
import argparse
import pickle
from network import PGGAN
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model_dir", type=str, default="gan_synth_model")
parser.add_argument("--batch_size", type=int, default=8)
parser.add_argument("--total_steps", type=int, default=1000000)
parser.add_argument("--gpu", type=str, default="0")
args = parser.parse_args()

tf.logging.set_verbosity(tf.logging.INFO)

with tf.Graph().as_default():

    pggan = PGGAN(
        min_resolution=[2, 16],
        max_resolution=[128, 1024],
        min_channels=32,
        max_channels=256,
        growing_level=tf.cast(tf.divide(
            x=tf.train.create_global_step(),
            y=args.total_steps
        ), tf.float32)
    )

    with open("pitch_counts.pickle", "rb") as file:
        pitch_counts = pickle.load(file)

    images = pggan.generator(
        latents=tf.random_normal([args.batch_size, 256]),
        labels=tf.one_hot(tf.reshape(tf.multinomial(
            logits=tf.log([tf.cast(list(zip(*sorted(pitch_counts.items())))[1], tf.float32)]),
            num_samples=args.batch_size
        ), [args.batch_size]), len(pitch_counts))
    )

    with tf.train.SingularMonitoredSession(
        scaffold=tf.train.Scaffold(
            init_op=tf.global_variables_initializer(),
            local_init_op=tf.group(
                tf.local_variables_initializer(),
                tf.tables_initializer()
            )
        ),
        checkpoint_dir=args.model_dir,
        config=tf.ConfigProto(
            gpu_options=tf.GPUOptions(
                visible_device_list=args.gpu,
                allow_growth=True
            )
        )
    ) as session:

        magnitude_spectrogram_dir = Path("samples/magnitude_spectrograms")
        instantaneous_frequency_dir = Path("samples/instantaneous_frequencies")

        if not magnitude_spectrogram_dir.exists():
            magnitude_spectrogram_dir.mkdir(parents=True, exist_ok=True)
        if not instantaneous_frequency_dir.exists():
            instantaneous_frequency_dir.mkdir(parents=True, exist_ok=True)

        def linear_map(inputs, in_min, in_max, out_min, out_max):
            return out_min + (inputs - in_min) / (in_max - in_min) * (out_max - out_min)

        for image in session.run(images):
            skimage.io.imsave(
                fname=magnitude_spectrogram_dir / "{}.jpg".format(len(list(magnitude_spectrogram_dir.glob("*.jpg")))),
                arr=linear_map(image[0], -1.0, 1.0, 0.0, 255.0).astype(np.uint8).clip(0, 255)
            )
            skimage.io.imsave(
                fname=instantaneous_frequency_dir / "{}.jpg".format(len(list(instantaneous_frequency_dir.glob("*.jpg")))),
                arr=linear_map(image[1], -1.0, 1.0, 0.0, 255.0).astype(np.uint8).clip(0, 255)
            )
