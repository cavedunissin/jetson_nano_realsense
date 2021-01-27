from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import io
import re
import time
import cv2
import json
import random

import pyrealsense2 as rs

import numpy as np

from PIL import Image
from tflite_runtime.interpreter import Interpreter

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

def load_labels(path):
  """Loads the labels file. Supports files with or without index numbers."""
  with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    labels = {}
    for row_number, content in enumerate(lines):
      pair = re.split(r'[:\s]+', content.strip(), maxsplit=1)
      if len(pair) == 2 and pair[0].strip().isdigit():
        labels[int(pair[0])] = pair[1].strip()
      else:
        labels[row_number] = pair[0].strip()
  return labels


def set_input_tensor(interpreter, image):
  """Sets the input tensor."""
  tensor_index = interpreter.get_input_details()[0]['index']
  input_tensor = interpreter.tensor(tensor_index)()[0]
  input_tensor[:, :] = image


def get_output_tensor(interpreter, index):
  """Returns the output tensor at the given index."""
  output_details = interpreter.get_output_details()[index]
  tensor = np.squeeze(interpreter.get_tensor(output_details['index']))
  return tensor


def detect_objects(interpreter, image, threshold):
  """Returns a list of detection results, each a dictionary of object info."""
  set_input_tensor(interpreter, image)
  interpreter.invoke()

  # Get all output details
  boxes = get_output_tensor(interpreter, 0)
  classes = get_output_tensor(interpreter, 1)
  scores = get_output_tensor(interpreter, 2)
  count = int(get_output_tensor(interpreter, 3))

  results = []
  for i in range(count):
    if scores[i] >= threshold:
      result = {
          'bounding_box': boxes[i],
          'class_id': classes[i],
          'score': scores[i]
      }
      results.append(result)
  return results

def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument(
      '--model', help='File path of .tflite file.', required=True)
  parser.add_argument(
      '--labels', help='File path of labels file.', required=True)
  parser.add_argument(
      '--threshold',
      help='Score threshold for detected objects.',
      required=False,
      type=float,
      default=0.3)
  args = parser.parse_args()

  # Configure depth and color streams
  pipeline = rs.pipeline()
  config = rs.config()
  config.enable_stream(rs.stream.depth, CAMERA_WIDTH, CAMERA_HEIGHT, rs.format.z16, 30)
  config.enable_stream(rs.stream.color, CAMERA_WIDTH, CAMERA_HEIGHT, rs.format.bgr8, 30)

  # Start streaming
  pipeline.start(config)

  labels = load_labels(args.labels)

  # interpreter = tf.lite.Interpreter(args.model)
  interpreter = Interpreter(args.model)

  interpreter.allocate_tensors()
  _, input_height, input_width, _ = interpreter.get_input_details()[0]['shape']

  key_detect = 0
  times=1
  while (key_detect==0):

    # Wait for a coherent pair of frames: depth and color
    frames = pipeline.wait_for_frames()
    depth_frame = frames.get_depth_frame()
    color_frame = frames.get_color_frame()
    if not depth_frame or not color_frame:
      continue

    # Convert images to numpy arrays
    depth_image = np.asanyarray(depth_frame.get_data())
    color_image = np.asanyarray(color_frame.get_data())

    image = cv2.resize(color_image, (input_width, input_height))

    if (times==1):
      results = detect_objects(interpreter, image, args.threshold)

      # print("Length of results = " ,len(results))

      for num in range(len(results)) :
        label_id=int(results[num]['class_id'])
        box_top=int(results[num]['bounding_box'][0] * CAMERA_HEIGHT)
        box_left=int(results[num]['bounding_box'][1] * CAMERA_WIDTH)
        box_bottom=int(results[num]['bounding_box'][2] * CAMERA_HEIGHT)
        box_right=int(results[num]['bounding_box'][3] * CAMERA_WIDTH)

        point_distance = 0.000
        for point_num in range(500):
          POINT_X = np.random.randint(box_left,box_right)
          POINT_Y = np.random.randint(box_top,box_bottom)
          if (POINT_X > CAMERA_WIDTH-1):
            POINT_X = CAMERA_WIDTH-1
          if (POINT_X < 0):
            POINT_X = 0
          if (POINT_Y > CAMERA_HEIGHT-1):
            POINT_Y = CAMERA_HEIGHT-1
          if (POINT_Y < 0):
            POINT_Y = 0
          print(POINT_X,',',POINT_Y)
          point_distance = point_distance + depth_frame.get_distance(POINT_X, POINT_Y)
          print(point_distance)
        
        point_distance = np.round(point_distance/500, 3)

        label_text = labels[label_id] +' score=' +str(round(results[num]['score'],3))
        distance_text = str(np.round(point_distance,3)) + 'm'

        cv2.rectangle(color_image, (box_left,box_top), (box_right,box_bottom), (255,255,0), 3)

        cv2.putText(color_image, label_text, (box_left,box_top+20),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,255),2,cv2.LINE_AA)
        cv2.putText(color_image, distance_text, (box_left,box_top+40),cv2.FONT_HERSHEY_SIMPLEX,0.6, (0,255,255), 2, cv2.LINE_AA)

        # print(results[num],labels[label_id])
        # print(box_left,box_top,box_right,box_bottom)
        # print("***************************************************************")

      show_img = cv2.resize(color_image,(int(CAMERA_WIDTH*2),int(CAMERA_HEIGHT*2)))
      cv2.imshow('Object Detecting....',show_img)

    times=times+1
    if (times>1) :
      times=1

    if cv2.waitKey(1) & 0xFF == ord('q'):
      key_detect = 1

  cv2.destroyAllWindows()
  pipeline.stop()

if __name__ == '__main__':
  main()
