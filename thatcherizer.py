"""
Thatcherizer App
take photo, detect eyes/mouth, flip, arrange, print

-jjm 3/18/2016
"""


import sys
import os
import re
import traceback
from os.path import splitext, join, isfile
from subprocess import call
import math
import numpy as np
import pygame
import Image
from thatcherizerTools import *

##### CONFIG VARS ##########################################
# dirs
thatcherDir = os.path.abspath(os.path.dirname(sys.argv[0]))
outputDir = join(thatcherDir, 'output')
stimsDir = join(thatcherDir, 'stims')
for d in [outputDir, stimsDir]:
	if not os.path.isdir(d): os.makedirs(d)

# settings
size = width, height = 800, 480
fps = 15
actual_fps = 0
centerX, centerY = width/2, height/2
viewerSize = (400,400)			# define the size of the viewer centered on the screen

# colors
black = (0,0,0)
white = (255,255,255)
yellow = (246, 238, 28)
bgBlue = (51,55,135)
ltBlue  = (108,190,220)

# initialize camera
camResolution = (640,480)		# specify resolution of the camera
imgCenterX, imgCenterY = camResolution[0]/2, camResolution[1]/2

useCamera = True
if useCamera:
	camStream = PiCamStream(camResolution, fps)
	camStream.start()
else:
	dummyImage = Image.open(join(stimsDir,"tmp2.jpg"))
	dummyImage = np.array(dummyImage)

# initialize misc
pygame.font.init()

# load BGs
introBg = pygame.image.load(join(stimsDir, 'introBg.png'))
takePhotoBg = pygame.image.load(join(stimsDir, 'takePhotoBg.png'))
confirmPhotoBg = pygame.image.load(join(stimsDir, 'confirmPhotoBg.png'))
confirmFeaturesBg = pygame.image.load(join(stimsDir, 'confirmFeaturesBg.png'))
resultsBg = pygame.image.load(join(stimsDir, 'resultsBg.png'))
printBg = pygame.image.load(join(stimsDir, 'printBg.png'))

# load stims
headGuide = pygame.image.load(join(stimsDir, 'headGuide.png'))
headGuide = pygame.transform.scale(headGuide, viewerSize)
mask = Image.open(join(stimsDir, "alphaMask.png"))



###### INITIALIZE PYGAME MAIN APP LOOP #################################
def run_thatcherizer(width, height, fps, starting_state):
	""" function to initialize and run the Thatcherizer App """

	# initialize pygame
	pygame.init()
	screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
	clock = pygame.time.Clock()

	# custom cursor
	cursorString = (
	"XX      ",
	"XX      ",
	"        ",
	"        ",
	"        ",
	"        ",
	"        ",
	"        ")
	myCursor, cursorMask = pygame.cursors.compile(cursorString, "X")
	pygame.mouse.set_cursor((8,8), (0,0), myCursor, cursorMask)

	# set which state to begin with
	activeState = starting_state

	# loop for as long as there's an active state
	while activeState != None:
		try:
			#### listen for all events
			killNow = False
			filteredEvents = []
			pressedKeys = pygame.key.get_pressed()
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					killNow = True
				elif event.type == pygame.KEYDOWN:
					if event.key == pygame.K_ESCAPE:
						killNow = True

				# clean quit, when asked
				if killNow:
					activeState.Terminate()
					if useCamera:
						camStream.stop()
					pygame.quit()
				else:
					# otherwise append the event to the list and pass along to the state
					filteredEvents.append(event)

			### Run through the 3 stages for the current state
			activeState.ProcessInput(filteredEvents)
			activeState.Update()
			activeState.Render(screen)

			### update the active state (will stay the same state if not updated by the activeState itself)
			activeState = activeState.next

			# update the display
			pygame.display.flip()
			clock.tick(fps)					# set the frame rate
			actual_fps = clock.get_fps()	# get the real frame rate

		except:
			exc_type, exc_val, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, file=sys.stdout)
			print exc_type
			print exc_val
			activeState.Terminate()
			if useCamera:
				camStream.stop()
			pygame.quit()
			raise SystemExit


###### DEFINE CLASSES FOR APP STATES #################################
class StateBase:
	""" Template class to base all app states off of """
	def __init__(self):
		self.next = self

	def ProcessInput(self, eventList):
		print("you didn't define ProcessInput for the current state")

	def Update(self):
		print("you didn't define Update for the current state")

	def Render(self, screen):
		print("you didn't define Render for the current state")

	def SwitchToState(self, nextState):
		""" method to update to define which state comes next """
		self.next = nextState

	def Terminate(self):
		""" clean quit. set next state to None """
		self.SwitchToState(None)


class thatchIntro(StateBase):
	""" Instruction and Start Screen State """
	def __init__(self):
		StateBase.__init__(self) 		# inherit structure from app state template

		# initialize buttons and store in list
		self.beginButton = Button("begin!", 281, 323, 70, upColor=white, hoverColor=yellow, downColor=yellow, fontColor=bgBlue, fontSize=30)

	def ProcessInput(self, eventList):	
		# look for button clicks in the event list
		for event in eventList:
			retVal = self.beginButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchLiveStream())

	def Update(self):
		pass

	def Render(self, screen):
		# draw the background
		screen.blit(introBg, (0,0))

		# render button states
		self.beginButton.draw(screen)



class thatchLiveStream(StateBase):
	""" Display live stream from camera with overlaid placement guide """
	def __init__(self):
		StateBase.__init__(self)		# inherit structre from app state template

		# initialize buttons
		self.resetButton = Button("reset", 700, int(height-90), 35, upColor=white, fontColor=bgBlue, fontSize=20)
		self.takePhotoButton = Button("take photo", 700, 241, 62, upColor=white, fontColor=bgBlue, fontSize=20)
		self.theseButtons = [self.resetButton, self.takePhotoButton]

	def ProcessInput(self,eventList):
		# look for button clicks in the event list
		for event in eventList:
			# reset button
			retVal = self.resetButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchIntro())

			# take photo button
			retVal = self.takePhotoButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchTakePhoto())

	def Update(self):
		# update the camera stream
		if useCamera:
			self.cameraFrame = camStream.read()											# get current frame
		else: 
			self.cameraFrame = dummyImage
		self.cameraImg = pygame.surfarray.make_surface(np.rot90(self.cameraFrame))	# convert to pygame surface (must rotate!)
		self.croppedImgRect = cropImage(self.cameraImg, viewerSize)

	def Render(self, screen):
		# draw the background
		screen.blit(takePhotoBg, (0,0))

		# show camera stream
		screen.blit(self.cameraImg, (centerX-(viewerSize[0]/2), centerY-(viewerSize[1]/2)), self.croppedImgRect)

		# show head guide
		screen.blit(headGuide, ( (centerX-(headGuide.get_rect().size[0]/2)), (centerY-(headGuide.get_rect().size[1]/2)) ))

		# render button states
		for button in self.theseButtons:
			button.draw(screen)


class thatchTakePhoto(StateBase):
	""" Display countdown screen and take photo """ 
	def __init__(self):
		StateBase.__init__(self)		# inherit structure form app state template

		# countdown parameters
		self.countdown = 3
		self.frameCount = 0

		# initialize text
		self.countdownFont = pygame.font.Font('freesansbold.ttf', 85)

	def ProcessInput(self,eventList):
		# don't process any user input during this state
		pass 

	def Update(self):
		# check if countdown has elapsed
		if self.countdown > 0:
			# update the camera stream
			if useCamera:
				self.cameraFrame = camStream.read()											# get current frame
			else: 
				self.cameraFrame = dummyImage								
			self.cameraImg = pygame.surfarray.make_surface(np.rot90(self.cameraFrame))	
			self.croppedImgRect = cropImage(self.cameraImg, viewerSize)

			# update the countdown
			self.TextSurf, self.TextRect = text_objects(str(self.countdown), self.countdownFont, yellow)
			self.TextRect.center = ((width/2), (height/2))

		else:
			# reset countdown
			self.countdown = 3

			# switch to the next state
			self.SwitchToState(thatchConfirmPhoto(self.cameraFrame, self.croppedImgRect))

		# update the counter
		self.frameCount += 1
		if self.frameCount > 5:				# CHANGE THIS BACK TO 15
			self.countdown -= 1
			self.frameCount = 0


	def Render(self, screen):
		# draw the background
		screen.blit(takePhotoBg, (0,0))

		# update the viewWindow
		screen.blit(self.cameraImg, (centerX-(viewerSize[0]/2), centerY-(viewerSize[1]/2)), self.croppedImgRect)

		# show head guide
		screen.blit(headGuide, ( (centerX-(headGuide.get_rect().size[0]/2)), (centerY-(headGuide.get_rect().size[1]/2)) ))

		# update the text 
		screen.blit(self.TextSurf, self.TextRect)


class thatchConfirmPhoto(StateBase):
	""" Display the photo and ask for confirmation """
	def __init__(self, cameraFrame, cropRect):
		StateBase.__init__(self)				# inherit structure from app state template
		
		# load in photo & rect
		self.cameraFrame = cameraFrame
		self.cameraImg = pygame.surfarray.make_surface(np.rot90(self.cameraFrame))
		self.cropRect = cropRect

		# fade in parameters
		self.flash = pygame.Surface((viewerSize[0], viewerSize[1]))
		self.alphaLevel = 255
		self.fadeStep = 20

		# initialize buttons
		self.doOverButton = Button("try again", 700, int(height-90), 45, upColor=white, fontColor=bgBlue, fontSize=18)
		self.acceptButton = Button("use this!", 700, 241, 62, upColor=white, fontColor=bgBlue, fontSize=20)
		self.theseButtons = [self.doOverButton, self.acceptButton]

	def ProcessInput(self,eventList):
		# look for button clicks in the event list
		for event in eventList:
			# reset button
			retVal = self.doOverButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchLiveStream())

			# confirm this photo, button
			retVal = self.acceptButton.handleEvent(event)
			if 'click' in retVal:
				# detect features in this photo
				self.detectFeatures = FeatureRecognition(self.cameraFrame)		# create featureDetection object with this frame
				self.eyeRects = self.detectFeatures.detectEyes()				# find the eyes in this image
				self.mouthRect = self.detectFeatures.detectMouth()				# find the mouth in this image

				# create feature objects for all features
				self.leftEye = FacialFeature("left eye", convertRect_image2screen(self.eyeRects[0]))
				self.rightEye = FacialFeature("right eye", convertRect_image2screen(self.eyeRects[1]))
				self.mouth = FacialFeature("mouth", convertRect_image2screen(self.mouthRect))
				self.features = [self.leftEye, self.rightEye, self.mouth]

				# switch to confirm features state
				self.SwitchToState(thatchConfirmFeatures(self.cameraFrame, self.cropRect, self.features))

	def Update(self):
		# update the flash alpha level
		if self.alphaLevel > 0:
			self.alphaLevel = self.alphaLevel - self.fadeStep
		elif self.alphaLevel < 0:
			self.alphaLevel = 0

	def Render(self, screen):
		# draw the background
		screen.blit(confirmPhotoBg, (0,0))

		# draw the photo
		screen.blit(self.cameraImg, (centerX-(viewerSize[0]/2), centerY-(viewerSize[1]/2)), self.cropRect)

		# draw flash
		self.flash.set_alpha(self.alphaLevel)
		self.flash.fill((255,255,255))
		screen.blit(self.flash, (centerX-(viewerSize[0]/2), centerY-(viewerSize[1]/2)))

		# render button states
		for button in self.theseButtons:
			button.draw(screen)


class thatchConfirmFeatures(StateBase):
	""" Confirm the selection of the eyes and mouth """
	def __init__(self, cameraFrame, cropRect, featureList):
		StateBase.__init__(self)

		# load in the photo, crop rect, and feature list
		self.cameraFrame = cameraFrame
		self.cameraImg = pygame.surfarray.make_surface(np.rot90(self.cameraFrame))
		self.cropRect = cropRect

		# initialize features
		self.featureList = featureList
		self.featureIndex = 0
		self.currentFeature = self.featureList[self.featureIndex]

		# initialize the text
		self.labelText = pygame.font.Font('freesansbold.ttf', 38)
		self.textSurf, self.textRect = text_objects(self.currentFeature.label, self.labelText, ltBlue)
		self.textRect.center = (700, 115)

		# initialize buttons
		self.nextButton = Button("next", 700, 241, 62, upColor=white, fontColor=bgBlue, fontSize=30)

	def ProcessInput(self, eventList):
		# send events to the buttons and features
		for event in eventList:

			# next button
			retVal = self.nextButton.handleEvent(event)
			if 'click' in retVal:
				self.featureIndex += 1 	# move to the next feature
				
				# if you've gone through all 3 features
				if self.featureIndex == len(self.featureList): 
					# build a list of all feature rectangles
					self.rectList = []
					for f in self.featureList:
						self.rectList.append(f.currentRect)				# note: currentRect returns SCREEN COORDINATES

					# thatcherize the photo!	
					self.orig_img, self.thatch_img = thatcherizePhoto(self.cameraFrame, self.rectList)

					# update to the showResults State
					self.SwitchToState(thatchShowResults(self.orig_img, self.thatch_img))
			
			# send the event to the current feature 
			self.currentFeature.handleEvent(event)

	def Update(self):
		# update the current feature parameters
		if self.featureIndex < len(self.featureList):
			self.currentFeature = self.featureList[self.featureIndex]
			self.textSurf, self.textRect = text_objects(self.currentFeature.label, self.labelText, ltBlue)
			self.textRect.center = (700, 115)

		self.currentRect = self.currentFeature.get_rect()	

	def Render(self,screen):
		# draw the background
		screen.blit(confirmFeaturesBg, (0,0))

		# draw the button
		self.nextButton.draw(screen)

		# draw the photo
		screen.blit(self.cameraImg, (centerX-(viewerSize[0]/2), centerY-(viewerSize[1]/2)), self.cropRect)

		# draw the rectangle for the current feature
		pygame.draw.rect(screen, self.currentFeature.color, self.currentRect, 3)

		# draw the current feature label text
		screen.blit(self.textSurf, self.textRect)


class thatchShowResults(StateBase):
	""" Show the results to the screen. Options to rotate, print, or start over """
	def __init__(self, origImgArray, thatchImgArray):
		StateBase.__init__(self)

		# load in the image arrays, convert to surfs
		self.origImgArray = origImgArray
		self.thatchImgArray = thatchImgArray

		# center pts for images
		self.leftImageCenter = (200,240)
		self.rightImageCenter = (600, 240)

		# convert arrays to reference images that can be copied and rotated
		self.origImgSurf_ref = pygame.surfarray.make_surface(np.rot90(self.origImgArray))
		self.origImgRect = self.origImgSurf_ref.get_rect(center=self.leftImageCenter)
		
		self.thatchImgSurf_ref = pygame.surfarray.make_surface(np.rot90(self.thatchImgArray))
		self.thatchImgSurf_ref = pygame.transform.rotate(self.thatchImgSurf_ref, 180)			# thatcherized is inverted at first
		self.thatchImgRect = self.thatchImgSurf_ref.get_rect(center=self.rightImageCenter)

		self.cropRect = (30, 40, 300, 400)

		# set initial rotation settings
		self.origImgSurf = self.origImgSurf_ref.copy()
		self.thatchImgSurf = self.thatchImgSurf_ref.copy()
		self.rotateNow = False
		self.angleStep = 30
		self.angle = 0

		# initialize buttons
		self.flipButton = Button("flip", int(width*.5), int(height*.5), 35, upColor=ltBlue, hoverColor=white, fontColor=yellow, fontSize=30)
		self.printButton = Button("print", int(width*.5), int(height*.2), 35, upColor=ltBlue, hoverColor=white, fontColor=bgBlue, fontSize=20)
		self.resetButton = Button("reset", int(width-23), int(height-23), 20, upColor=ltBlue, hoverColor=white, fontColor=bgBlue, fontSize=14)

	def ProcessInput(self, eventList):
		# send events to the buttons
		for event in eventList:
			# rotate button
			retVal = self.flipButton.handleEvent(event)
			if 'click' in retVal: self.rotateNow = True

			# print button
			retVal = self.printButton.handleEvent(event)
			if 'click' in retVal:
				self.SwitchToState(thatchPrintResults(self.origImgArray, self.thatchImgArray))

			# reset button 
			retVal = self.resetButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchIntro())

	def Update(self):
		# flip the images when needed
		if self.rotateNow:
			self.angle = self.angle + self.angleStep
			if self.angle <= 180:
				self.origImgSurf = pygame.transform.rotate(self.origImgSurf_ref, self.angle)
				self.origImgRect = self.origImgSurf.get_rect(center=self.origImgRect.center)
				
				self.thatchImgSurf = pygame.transform.rotate(self.thatchImgSurf_ref, self.angle)
				self.thatchImgRect = self.thatchImgSurf.get_rect(center=self.thatchImgRect.center)

			elif self.angle > 180:
				self.origImgSurf_ref = self.origImgSurf 				# after each rotation, update the reference images
				self.thatchImgSurf_ref = self.thatchImgSurf

				# reset rotation settings
				self.rotateNow = False 
				self.angle = 0

	def Render(self,screen):
		# draw the images
		screen.blit(self.origImgSurf, self.origImgRect) #, self.cropRect)		# left
		screen.blit(self.thatchImgSurf, self.thatchImgRect)

		# draw the flip buttons
		self.flipButton.draw(screen)

		# draw the background (NOTE: has transparency -- needs to be drawn after flip button)
		screen.blit(resultsBg, (0,0))

		# draw the remaining buttons
		self.printButton.draw(screen)
		self.resetButton.draw(screen)


class thatchPrintResults(StateBase):
	""" Show the print screen with a start over button """
	def __init__(self, origImgArray, thatchImgArray):
		StateBase.__init__(self)

		# load the image arrays
		self.origImgArray = origImgArray
		self.thatchImgArray = thatchImgArray

		# initilize timer
		self.timer = 0

		#initialize buttons
		self.resetButton = Button("Start Over", 345, 310, 70, upColor=white, fontColor=bgBlue, fontSize=26)

	def ProcessInput(self, eventList):
		# send events to the buttons
		for event in eventList:
			# start over button
			retVal = self.resetButton.handleEvent(event)
			if 'click' in retVal: self.SwitchToState(thatchIntro())

	def Update(self):
		# update timer
		self.timer += 1

		# this is just to hide the processing lag with assembleCompositeImage in the final screen
		if self.timer == 2:
			assembleCompositeImage(self.origImgArray, self.thatchImgArray) 			# run the code to built the print image
			printComposite()												# print!

	def Render(self,screen):
		# draw the background
		screen.blit(printBg, (0,0))

		# draw the buttons
		self.resetButton.draw(screen)


###### IN-APP CLASSES/FUNCTIONS ###############################################
class Button(object):
	""" Button creator """
	def __init__(self, label=None, x=0, y=0, r=50, upColor=yellow, hoverColor=ltBlue, downColor=ltBlue, fontColor=white, fontSize=20):
		self.label = label
		self.x = x
		self.y = y
		self.r = r
		self.upColor = upColor
		self.hoverColor = hoverColor
		self.downColor = downColor
		self.fontColor = fontColor
		self.fontSize = fontSize

		# define text
		if self.label != None:
			self.buttonText = pygame.font.Font('freesansbold.ttf', self.fontSize)
			self.textSurf, self.textRect = text_objects(self.label, self.buttonText, self.fontColor)
			self.textRect.center = (self.x, self.y)

		# button state
		self.buttonDown = False
		self.mouseOverButton = False
		self.mouseHovering = False

	
	def draw(self, screen):
		""" draw the current state of the button """
		
		# set color based on mouse events
		if self.buttonDown:
			self.buttonColor = self.downColor
		elif self.mouseHovering:
			self.buttonColor = self.hoverColor		
		else:
			self.buttonColor = self.upColor

		# draw the button circle
		pygame.draw.circle(screen, self.buttonColor, (self.x, self.y), self.r)

		# draw button label (if any)
		if self.label != None:
			screen.blit(self.textSurf, self.textRect)

	def handleEvent(self, event):
		""" set behaviors following events """
		
		retVal = []
		hasExited = False
		# check if its a mouse event:
		if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
 			
 			# get mouse position
			self.mousePos = event.pos
			self.dist = math.hypot(self.mousePos[0]-self.x, self.mousePos[1]-self.y)
			
			# if mouse has entered the button for the first time
			if (self.dist < self.r) and (self.mouseOverButton == False):
				self.mouseOverButton = True
				retVal.append('enter')

			# if mouse has left the button after having been over it
			elif (self.dist > self.r) and (self.mouseOverButton == True):
				self.mouseOverButton = False
				hasExited = True

			# if the event happend with the mouse over the button
			if (self.dist < self.r):
				if event.type == pygame.MOUSEMOTION:
					self.mouseHovering = True
					retVal.append('move')
				elif event.type == pygame.MOUSEBUTTONDOWN:
					self.buttonDown = True
					self.lastMouseButtonDownOverButton = True
					retVal.append('down')
			else:
				if event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN):
					self.lastMouseButtonDownOverButton = False

			# handle MOUSEUP regardless of whether it was over the button or now
			mouseClicked = False
			if event.type == pygame.MOUSEBUTTONUP:
				if self.lastMouseButtonDownOverButton:
					mouseClicked = True
				self.lastMouseButtonDownOverButton = False		# reset

				if self.buttonDown:
					self.buttonDown = False		# reset self.buttonDown
					retVal.append('up')

				if mouseClicked:
					self.buttonDown = False
					retVal.append('click')

		if hasExited:
			self.mouseHovering = False
			retVal.append('exit')

		return retVal


def text_objects(text, font, color):
	""" convert the supplied text to a text surface """
	textSurface = font.render(text, True, color)
	return textSurface, textSurface.get_rect()


def cropImage(img, windowSize):
	""" crop the supplied image & center within specified window; return Rect """
	# find center coords of image
	imgCenterX, imgCenterY = img.get_rect().center

	# calculate the upper left corner coords for crop mark
	x1 = imgCenterX - (windowSize[0]/2)
	y1 = imgCenterY - (windowSize[1]/2)

	# return Rect (x1, y1, width, height)
	cropRect = (x1, y1, windowSize[0], windowSize[1])
	return cropRect


def get_lastFileNumber():
	""" return the last file number used in output names """
	fileNum = 0
	for f in os.listdir(outputDir):
		if isfile(join(outputDir, f)):
			fname, ext = splitext(f)
			if re.search("img_*", fname):
				this_fileNum = fname[4:7]
				if this_fileNum > fileNum:
					fileNum = this_fileNum
	return str(int(fileNum)).zfill(3)


def convertRect_screen2image(Rect):
	""" convert the supplied screen rect to image coordinates """
	
	newRect = []
	# convert x1
	newRect.append(imgCenterX - (centerX-Rect[0]))

	# convert y1
	newRect.append(imgCenterY - (centerY-Rect[1]))

	# width, height
	newRect.append(Rect[2])
	newRect.append(Rect[3])

	return newRect


def convertRect_image2screen(Rect):
	""" convert the suppled image rect to screen coordinates """
	newRect = []

	# convert x1
	newRect.append(Rect[0] + (centerX-imgCenterX))

	# convert y1 
	newRect.append(Rect[1] + (centerY-imgCenterY))

	# width, height
	newRect.append(Rect[2])
	newRect.append(Rect[3])

	return newRect


def thatcherizePhoto(imgArray, rectList):
	""" 
	for each rectangle in the supplied rectList, crop, flip, and alpha mask, and save
		- input rectangles are in SCREEN COORDINATES
		- input imgArray is converted to PIL Image type
	"""
	# convert the input imgArray to PIL type
	imgOrig = Image.fromarray(np.fliplr(imgArray))
	imgThatch = imgOrig.copy()			# create a copy that will be thatcherized

	# loop through each Rect (L.eye, R.eye, Mouth):
	for r in rectList:
		# convert rect to image coordinates
		cr = convertRect_screen2image(r)
		cr_w = cr[2]			# width, for clarity later
		cr_h = cr[3]			# height, for clarity later

		# resize the mask to fit the current rectangle
		resizedMask = mask.resize((cr[2], cr[3]))

		# crop rect out of original image 
		imgCrop = imgThatch.crop((cr[0], cr[1], cr[0]+cr_w, cr[1]+cr_h))

		# paste flipped version fo imgCrop back into the original, using the resized alpha mask
		imgThatch.paste(imgCrop.transpose(Image.FLIP_TOP_BOTTOM), (cr[0], cr[1]), resizedMask)

	# crop these images to be a 360x480 (w,h) rect around the face
	cropBox = (140,0,500,480)
	imgOrig = imgOrig.crop(cropBox)		
	imgThatch = imgThatch.crop(cropBox)

	# save the original and thatcherized images, as well as the final assembled print
	lastFileNumber = get_lastFileNumber()	# get the base name to use for these images
	currentFileNumber = str(int(lastFileNumber)+1).zfill(3)
	fname = ("img_" + currentFileNumber)
	
	imgOrig.save(join(outputDir, (fname + "_orig.png")))
	imgThatch.save(join(outputDir, (fname + "_thatch.png")))

	# return the orig and thatcherized as arrays
	return np.fliplr(np.array(imgOrig)), np.fliplr(np.array(imgThatch))

def assembleCompositeImage(imgOrigArray, imgThatchArray):
	""" 
	Crop the original and thatcherized, and place in proper locaton on the print template. 
	save the final assembled composite. 

	inputs: PIL image format for both original and thatcherized image.
	"""

	# convert the arrays to PIL image type
	imgOrig = Image.fromarray(np.fliplr(imgOrigArray))
	imgThatch = Image.fromarray(np.fliplr(imgThatchArray))

	# scale the images up for the high-res print template file
	imgOrig = imgOrig.resize((720, 960))
	imgThatch = imgThatch.resize((720, 960))

	# crop to 640x428 (w,h). This is a 320x426 crop of the original resolution
	cropBox = (40, 52, 680, 908)	# (x1, y1, x2, y2) of the crop. 
	imgOrig = imgOrig.crop(cropBox)
	imgThatch = imgThatch.crop(cropBox)

	# rotate the thatcherized 
	imgThatch = imgThatch.rotate(180)

	# place into print template
	printTemplate = Image.open(join(stimsDir, "printTemplates", "printTemplate.png"))
	printTemplate.paste(imgOrig, (58,172))
	printTemplate.paste(imgThatch, (1102,172))

	# save
	fname =  "img_" + get_lastFileNumber() + "_composite.png"
	printTemplate.save(join(outputDir, fname))	

	return printTemplate


def printComposite():
	"""
	send the composite to the printer
	"""
	compositeName = "img_" + get_lastFileNumber() + "_composite.png"
	printerName = "Canon_C910"
	print compositeName
	#call(['lp', '-d', printerName, join(outputDir, compositeName)])







### Run the App, starting with the Intro ##################################
run_thatcherizer(width, height, fps, thatchIntro())




