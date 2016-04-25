"""
Set of additional helper functions for running the Thatcherizer app

-jjm 3/18/2016
"""

import sys
import os
from os.path import join, split
import picamera
from picamera.array import PiRGBArray
import random
import numpy as np
import io
import Image
import cv2
import time
import pygame
from pygame.locals import *
from threading import Thread



###################### INTERACT WITH CAMERA #############################
class PiCamStream:
	""" Class for interacting with the Pi Camera stream """
	def __init__(self, resolution, fps):
		""" initialize the camera """

		self.resolution = resolution
		self.camera = picamera.PiCamera()
		self.camera.framerate=fps
		#self.camera.hflip=True
		#self.camera.vflip=True
		self.camera.resolution = self.resolution
		self.rawCapture = PiRGBArray(self.camera, size=self.resolution)

		self.stream = self.camera.capture_continuous(self.rawCapture, format="rgb", use_video_port=True)

		self.frame = None
		self.stopped = False

	def start(self):
		""" start the thread to read frames from the video stream """
		Thread(target=self.update, args=()).start()
		return self

	def update(self):
		""" keep looping til thread is stopped """
		for f in self.stream:
			self.frame = f.array
			self.rawCapture.truncate(0)		# clear the stream

			if self.stopped:
				self.stream.close()
				self.rawCapture.close()
				self.camera.close()
				return

	def read(self):
		""" return the most recent frame """
		return self.frame
	
	def stop(self):
		""" stop the thread """
		self.stopped = True


###################### DETECT FACIAL FEATURES #############################
class FeatureRecognition:
	""" Detect Eyes/Mouth on the the supplied imgArray """
	def __init__(self, imgArray):
		""" input imgArray: (height, width) """

		# load in array (needs to be in (nRows, nCols) format; not (width, height))
		self.imgArray = imgArray
		self.imgArray = np.fliplr(self.imgArray)
		self.imgCenterX, self.imgCenterY = self.imgArray.shape[1]/2, self.imgArray.shape[0]/2
		self.imgArrayGray = cv2.cvtColor(self.imgArray, cv2.COLOR_RGB2GRAY)	# convert to grayscale

		# set default (x,y,w,h) locations for feature rects (based on head guide) [IMAGE COORDINATES]
		self.leftEyeRect = (240, 155, 50, 30)
		self.rightEyeRect = (345, 155, 50, 30)
		self.mouthRect = (275, 255, 90, 60)

		# load in classifiers
		self.classifierDir = (join(os.getcwd(), 'classifiers'))
		if not os.path.isdir(self.classifierDir): 
			print ("you screwed up the classifier directory path, dude")
		self.face_cascade = cv2.CascadeClassifier(join(self.classifierDir, 'haarcascade_frontalface_default.xml'))
		self.eye_cascade = cv2.CascadeClassifier(join(self.classifierDir, "haarcascade_eye.xml"))
		self.mouth_cascade = cv2.CascadeClassifier(join(self.classifierDir, "haarcascade_mouth.xml"))

	def detectEyes(self):
		""" find the eyes; return list of eyeRect tuples [image coordinates] """
		self.eyeScaleFactor = 3.3
		self.eyeRectAspectRatio = 1.7  # factor by which the Rect is wider than tall

		# run classifier
		self.eyeRects = self.eye_cascade.detectMultiScale(self.imgArrayGray, self.eyeScaleFactor)
		if len(self.eyeRects) > 0:
			print "Found " + str(len(self.eyeRects)) + " Eyes!"
			# limit to only two eyes
			if len(self.eyeRects) > 2: self.eyeRects[:2]

			# loop through all eyes
			for (self.x,self.y,self.w,self.h) in self.eyeRects:
				self.eyeCenterX = self.x+self.w/2
				self.eyeCenterY = self.y+self.h/2

				# update the height so the Rect isn't a square
				self.h = int(self.w/self.eyeRectAspectRatio)
				self.y = self.y + ((self.w-self.h)/2)

				# figure out which side of the image it comes from
				if self.eyeCenterX <= self.imgCenterX:
					# left
					self.leftEyeRect = (self.x, self.y, self.w, self.h)
				elif self.eyeCenterX > self.imgCenterX:
					# right
					self.rightEyeRect = (self.x, self.y, self.w, self.h)

				
		# return list of (x,y,w,h) tuples describing the left and right eyes
		self.eyeRects = [self.leftEyeRect, self.rightEyeRect]	
		return self.eyeRects

	def detectMouth(self):
		""" find the mouth, return mouth rect [image coordinates] """
		self.mouthScaleFactor = 4

		# run classifier
		self.mouthRects = self.mouth_cascade.detectMultiScale(self.imgArrayGray, self.mouthScaleFactor)
		
		if len(self.mouthRects) > 0:
			print "Found Mouth!"
			self.foundMouth = False

			# loop through mouths, look for one on the lower half of the image
			for (self.x,self.y,self.w,self.h) in self.mouthRects:

				# check if its in lower half of image
				if self.y > self.imgCenterY:
					self.foundMouth = True

					# if so, update mouthRect and break
					self.mouthRect = (self.x,self.y,self.w,self.h)
					break

		# return (x,y,w,h) tuple describing the mouth rect
		return self.mouthRect


###################### FACIAL FEATURE OBJECTS #############################
class FacialFeature:
	def __init__(self, label, starting_rect):
		""" Class to draw and store rectangle for facial features (eyes, mouth). NOTE: Rects are in SCREEN COORDINATES """
		self.label = label

		# init mouse settings
		self.buttonDown = False
		self.pt1 = (starting_rect[0],starting_rect[1])
		self.pt2 = (self.pt1[0]+starting_rect[2], self.pt1[1]+starting_rect[3])

		# rect settings
		self.color = (np.random.randint(0,255), np.random.randint(0,255), np.random.randint(0,255),)
		self.currentRect = starting_rect
		self.isRect = True

	def handleEvent(self, event):
		""" use mouse clicks to handle the drawing of rectangles """

		if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):

			# if mouse is currently on the view screen
			if (event.pos[0] > 200) and (event.pos[0] < 600) and (event.pos[1] > 40) and (event.pos[1] < 440): 
				# if button down for the first time
				if event.type == pygame.MOUSEBUTTONDOWN and not self.buttonDown:
					self.buttonDown = True
					self.pt1 = event.pos
					self.isRect = False

				# if mouse moving while button is down
				if event.type == pygame.MOUSEMOTION and self.buttonDown:
					self.pt2 = event.pos
					self.isRect = True

				# if button up after button has been down
				if event.type == pygame.MOUSEBUTTONUP and self.buttonDown:
					self.buttonDown = False

	def get_rect(self):
		if self.isRect:
			# calculate the top left X coord of the rect, and rect width
			if self.pt1[0] < self.pt2[0]:
				self.x1 = self.pt1[0]
			else:
				self.x1 = self.pt2[0]
			self.rectWidth = abs(self.pt1[0] - self.pt2[0])

			# calculate the top left Y coord of the rect, and rect height
			if self.pt1[1] < self.pt2[1]:
				self.y1 = self.pt1[1]
			else:
				self.y1 = self.pt2[1]
			self.rectHeight = abs(self.pt1[1] - self.pt2[1])

			# define a rectangle with this info
			self.currentRect = [self.x1, self.y1, self.rectWidth, self.rectHeight]
			return self.currentRect
		else:
			return (0,0,0,0)


