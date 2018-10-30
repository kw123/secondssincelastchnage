#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# seconds since last change Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, re, Queue, threading, subprocess, pwd,urllib2
import datetime, time
import simplejson as json
from time import gmtime, strftime, localtime
import urllib
import fcntl
import signal
import copy
import versionCheck.versionCheck as VS
import myLogPgms.myLogPgms 




'''
how it works:
1. add/remove device/state/frequency to be tracked in config
2. loop every 0.2 seconds and check if nect device/state is due to be changed
3. compare device/state with old value
4. if different reset variable: seconds_deviceName_state to 0
   if same, increment variable

or subscribe to changes

5.
'''
Version="7.6.7"


_emptyDev={"states":{}}
_emptyState={"lastChange":0,"lastCheck":0,"checkFrequency":0,"lastValue":"", "'checkFrequency": 60, u"previousChange":0}

_emptyVar={"lastChange":0,"lastCheck":0,"checkFrequency":0,"lastValue":"", "'checkFrequency": 60, u"previousChange":0}


################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.pathToPlugin = os.getcwd() + "/"
		## = /Library/Application Support/Perceptive Automation/Indigo 6/Plugins/piBeacon.indigoPlugin/Contents/Server Plugin
		p = max(0, self.pathToPlugin.lower().find("/plugins/")) + 1
		self.indigoPath = self.pathToPlugin[:p]
		self.pluginState		= "init"
		self.pluginShortName 	= "secondsSinceLastChange"
		self.pluginVersion		= pluginVersion
		self.pluginId			= pluginId
	
	
	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
	
	########################################
	def startup(self):


		self.debugOptions = ["Logic","all","Config","Subscribe","Special"]

		major, minor, release = map(int, indigo.server.version.split("."))

		if  major < 7:
			indigo.server.log(u"need indigo version >7; running on : >>"+unicode(indigo.server.version)+u"<<")
			self.sleep(1000)
			exit()

		
		self.loopTest				= float(self.pluginPrefs.get("loopTest",2.0))
		self.subscribe				= self.pluginPrefs.get("subscribe","loop")
		self.variFolderName			= self.pluginPrefs.get("variFolderName","Seconds")
		self.devList				= json.loads(self.pluginPrefs.get("devList","{}"))
		self.varList				= json.loads(self.pluginPrefs.get("varList","{}"))

		for dd in self.devList:
			dev = indigo.devices[int(dd)]
			for ss in self.devList[dd]["states"]:
				self.createOrConfirmVariablesForDevice(dev,ss)
				if "previousChange" not in self.devList[dd]["states"][ss]:
					self.devList[dd]["states"][ss]["previousChange"] =0

		for dd in self.varList:
			var = indigo.variables[int(dd)]
			self.createOrConfirmVariablesForVariable(var)
			if "lastValue" not in self.varList[dd]:
				self.varList[dd]["lastValue"] = "-1"

	
		

		self.saveNow			= False
		self.devID				= 0
		self.quitNow			= "" # set to !="" when plugin should exit ie to restart, needed for subscription -> loop model
		self.stopConcurrentCounter = 0


		self.myPID = os.getpid()
		self.MACuserName   = pwd.getpwuid(os.getuid())[0]
		self.MAChome	   = os.path.expanduser("~")
		self.indigoHomeDir = self.MAChome+"/indigo/" #	this is the data directory

		self.indigoConfigDir	 = self.indigoHomeDir + self.pluginShortName+"/"

		self.pythonPath					= u"/usr/bin/python2.6"
		if os.path.isfile(u"/usr/bin/python2.7"):
			self.pythonPath				= u"/usr/bin/python2.7"


		if not os.path.exists(self.indigoHomeDir):
			os.mkdir(self.indigoHomeDir)

		if not os.path.exists(self.indigoConfigDir):
			os.mkdir(self.indigoConfigDir)
			if not os.path.exists(self.indigoConfigDir):
				self.errorLog("error creating the plugin data dir did not work, can not create: "+ self.indigoConfigDir)
				self.sleep(1000)
				exit()
		
		self.debugLevel = []
		for d in self.debugOptions:
			if self.pluginPrefs.get(u"debug"+d, False): self.debugLevel.append(d)

		self.ML = myLogPgms.myLogPgms.MLX()
		self.setLogfile(unicode(self.pluginPrefs.get("logFileActive2", "standard")))

		
		
		self.printConfigCALLBACK()
		self.pluginPrefs["devList"] = json.dumps(self.devList)
		self.pluginPrefs["varList"] = json.dumps(self.varList)
		
		return


	####-----------------	 ---------
	def setLogfile(self,lgFile):
		self.logFileActive = lgFile
		if   self.logFileActive =="standard":	self.logFile = ""
		elif self.logFileActive =="indigo":		self.logFile = self.indigoPath.split("Plugins/")[0]+"Logs/"+self.pluginId+"/plugin.log"
		else:									self.logFile = self.indigoConfigDir + self.pluginShortName+".log"
		self.ML.myLogSet(debugLevel = self.debugLevel ,logFileActive=self.logFileActive, logFile = self.logFile)

########################################


	########################################
	def deviceStartComm(self, dev):
		return
	
	########################################
	def deviceStopComm(self, dev):
		return
	########################################
	def stopConcurrentThread(self):
		self.stopConcurrentCounter +=1
		self.ML.myLog( text =u"stopConcurrentThread called " + str(self.stopConcurrentCounter))
		if self.stopConcurrentCounter ==1:
			self.stopThread = True



	########################################
	def variableUpdated(self, origVar, newVar):
		try:
			if self.subscribe !="subscribe": return
			varstr = str(origVar.id)
			if varstr not in self.varList: return

			now=time.time()
			sss =self.varList[varstr]
			varName= origVar.name
			if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = "checking variable: "+varName, mType="secs since..Subscribe" )

			if origVar.value != newVar.value: 
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(indigo.variables[origVar.id])

				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = " .. changed from:"+origVar.value+";  to:"+ newVar.value+";  secs_since last change: "+str(int(now - sss["lastChange"])), mType="secs since..Subscribe" )

				indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
				indigo.variable.updateValue(variNamePrevious, str(int(now - sss["lastChange"])))
				indigo.variable.updateValue(variName,"0")
				sss["lastValue"]		= newVar.value
				sss["previousChange"]	= sss["lastChange"]
				sss["lastChange"]		= now
				sss["lastCheck"] 		= now
		except	Exception, e:
				self.ML.myLog( text ="error in Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))

	

	########################################
	def deviceUpdated(self, origDev, newDev):
		try:
			if self.subscribe !="subscribe": return
			devstr = str(origDev.id)
			if devstr not in self.devList: return

			now=time.time()
			ddd =self.devList[devstr]
			devName= origDev.name
			if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = "checking device :"+devName, mType="secs since..Subscribe" )
			dev = indigo.devices[origDev.id]

			for state in self.devList[devstr]["states"]:
				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = ("   state: "+state).ljust(25)+";  old value:"+ unicode(origDev.states[state]), mType="secs since..Subscribe" )
				if state not in newDev.states: continue
				if origDev.states[state] == newDev.states[state]: continue
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
				sss = ddd["states"][state]
				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = "                           changed to:".ljust(38)+ unicode(newDev.states[state])+";  secs_since last change: "+str(int(now - sss["lastChange"])), mType="secs since..Subscribe" )

				indigo.variable.updateValue(variNamePrevious, str(int(now - sss["lastChange"])))
				indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"])
				indigo.variable.updateValue(variName,"0")
				sss["lastValue"]		= unicode(newDev.states[state])
				sss["previousChange"]	= sss["lastChange"]
				sss["lastChange"]		= now
				sss["lastCheck"]		= now
		except	Exception, e:
				self.ML.myLog( text ="error in Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))

		return
	

####-----------------  set the geneeral config parameters---------
	def validatePrefsConfigUi(self, valuesDict):

		self.variFolderName		= valuesDict[u"variFolderName"]
		self.loopTest			= float(valuesDict[u"loopTest"])
		xx= valuesDict[u"subscribe"]
		if xx != self.subscribe:
			if xx=="subscribe":
				indigo.devices.subscribeToChanges()
				indigo.variables.subscribeToChanges()
			else:
				self.quitNow="yes" # need to restart
				self.ML.myLog( text ="restart plugin needed to UNsubscribe to changes")

		self.subscribe = xx

		try:
			indigo.variables.folder.create(self.variFolderName)
		except:
			pass

		self.debugLevel = []
		for d in self.debugOptions:
			if valuesDict[ u"debug"+d] : self.debugLevel.append(d)
				

		self.setLogfile(valuesDict["logFileActive2"])

		return True, valuesDict


	########################################
	def dummyCALLBACK(self):
		
		return
	########################################
	def printConfigCALLBACK(self,devstr=""):
		if len(self.devList)> 0:
			self.ML.myLog( text ="Configuration")
			self.ML.myLog( text ="Dev-Name----------       ---------------State  Data----------", mType="DevID")
			for devid in self.devList:
				if devid == devstr or devstr=="":
					for state in self.devList[devid]["states"]:
						self.ML.myLog( text =  indigo.devices[int(devid)].name.ljust(25) +state.rjust(20)+"  "+ unicode(self.devList[devid]["states"][state]), mType=devid.ljust(10) )

		if len(self.varList)> 0:
			self.ML.myLog( text ="Configuration")
			self.ML.myLog( text ="Var-Name----------".ljust(25)+"  Data-------------", mType="VarID")
			for varid in self.varList:
				self.ML.myLog( text =  indigo.variables[int(varid)].name.ljust(25)+"  "+ unicode(self.varList[varid]), mType=varid.ljust(10))
		
		return
	########################################
	def pickDeviceCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.ML.decideMyLog(u"Config"): self.ML.myLog( text = unicode(valuesDict), mType="secs since..Config")
		self.devID= int(valuesDict["device"])
		return valuesDict

	########################################
	def filterStates(self,filter="",valuesDict="",typeId=""):				# Select only device/properties that are supported
	
		if self.devID ==0: return [(0,0)]
		retList=[]
		dev =  indigo.devices[self.devID]
		for state in dev.states.keys():
			retList.append((state, state))
		return retList

	########################################
	def pickVariableCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.ML.decideMyLog(u"Config"): self.ML.myLog( text = unicode(valuesDict), mType="secs since..Config")
		self.varID= int(valuesDict["variable"])
		return valuesDict



	########################################
	def buttonConfirmCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict["device"])]
		devstr= str(dev.id)
		if devstr not in self.devList:
			self.devList[devstr]				= copy.deepcopy(_emptyDev)
		
		state = valuesDict["state"]
		if	state not in self.devList[devstr]["states"]:
			self.devList[devstr]["states"][state]	=copy.deepcopy(_emptyState)
		
		self.devList[devstr]["states"][state]["checkFrequency"] = int(valuesDict["checkFrequency"])
		self.devList[devstr]["states"][state]["lastChange"]		= time.time()
		self.devList[devstr]["states"][state]["lastCheck"]		= 0
		self.saveNow=True
		self.createOrConfirmVariablesForDevice(indigo.devices[dev.id],state)
		
		self.printConfigCALLBACK(devstr=devstr)

		return valuesDict

		
	########################################
	def buttonRemoveCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict["device"])]
		devstr= str(dev.id)
		if devstr in self.devList:
			state = valuesDict["state"]
			if	state in self.devList[devstr]["states"]:
				del self.devList[devstr]["states"][state]
			if len(self.devList[devstr])==0:
				del self.devList[devstr]
			
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def buttonConfirmVARCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		var=indigo.variables[int(valuesDict["variable"])]
		varstr= str(var.id)
		if varstr not in self.varList:
			self.varList[varstr]				= copy.deepcopy(_emptyVar)
		
		self.varList[varstr]["checkFrequency"]	= int(valuesDict["checkFrequency"])
		self.varList[varstr]["lastChange"]		= time.time()
		self.varList[varstr]["lastCheck"]		= 0

		self.saveNow=True
		self.createOrConfirmVariablesForVariable(indigo.variables[var.id])
		self.printConfigCALLBACK(devstr=varstr)

		return valuesDict

	########################################
	def buttonRemoveVARCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		var=indigo.variables[int(valuesDict["variable"])]
		varstr= str(var.id)
		if varstr in self.varList:
			del self.varList[varstr]
	
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def createOrConfirmVariablesForDevice(self,dev,state):
		name					= dev.name.replace(" ","_")+"_"+state.replace(" ","_")
		variName				= name+"_seconds_since_change"
		variNamePrevious		= name+"_seconds_previous_change"
		variNamePreviousValue	= name+"_previous_value"
		try: 	indigo.variable.create(variName,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePrevious,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePreviousValue,str(dev.states[state]),self.variFolderName)
		except: pass
		return variName, variNamePrevious, variNamePreviousValue, unicode(dev.states[state])
		
	########################################
	def createOrConfirmVariablesForVariable(self,var):
		name					= var.name
		variName				= name+"_seconds_since_change"
		variNamePrevious		= name+"_seconds_previous_change"
		variNamePreviousValue	= name+"_previous_value"
		try: 	indigo.variable.create(variName,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePrevious,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePreviousValue,var.value,self.variFolderName)
		except: pass
		return variName, variNamePrevious, variNamePreviousValue, var.value


	########### main loop -- start #########
	########################################
	def runConcurrentThread(self):

		if self.subscribe =="subscribe":
			indigo.devices.subscribeToChanges()
			indigo.variables.subscribeToChanges()

		lastVcheckHour = -1
		lastSave=time.time()
		try:
			while self.quitNow =="":
				now = time.time()
				if self.saveNow or lastSave +60 < now:
					self.pluginPrefs["devList"] =json.dumps(self.devList)
					self.pluginPrefs["varList"] =json.dumps(self.varList)
					self.saveNow=False
				delList=[]	  
				for devID in self.devList:
					if int(devID) >0:
						try:
							dev= indigo.devices[int(devID)]
						except Exception, e:
						   if unicode(e).find("timeout") >-1: self.sleep(5)
						try:
							dev = indigo.devices[int(devID)]
						except:
								self.ML.myLog( text =" error; device with indigoID = "+ str(devID) +" does not exist, removing from tracking")
								delList.append(devID)
								continue
							   
					ddd =self.devList[devID]
					for state in ddd["states"]:
						sss = ddd["states"][state]
						variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
						
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = "name: "+dev.name+ "... lastCheck+checkFrequency: "+str(sss["lastCheck"])+ " + "+str(sss["checkFrequency"])+" < " +str(now)+"now", mType="secs since.. Logic" )
						if self.subscribe != "subscribe":
							if not( (sss["lastCheck"] + sss["checkFrequency"]) < now or value != sss["lastValue"]) : continue
						elif  not ( (sss["lastCheck"] + sss["checkFrequency"]) < now ) : continue
						
						sss["lastCheck"] = now
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = " ... data: "+unicode(ddd))
						

						if value != sss["lastValue"]:
							indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
							indigo.variable.updateValue(variName,"0")
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss["lastChange"]))) )
							sss["lastValue"]		= value
							sss["previousChange"]	= sss["lastChange"]
							sss["lastChange"]		= now
						elif (sss["lastChange"] + sss["checkFrequency"]) < now :
							indigo.variable.updateValue(variName, str(int(now-float(sss["lastChange"]))) )
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss["previousChange"]))) )
				for devID in delList:
					del self.devList[devID]


				delList=[]	  
				for varID in self.varList:
					if int(varID) >0:
						try:
							var= indigo.variables[int(varID)]
						except Exception, e:
						   if unicode(e).find("timeout") >-1: self.sleep(5)
						try:
							var = indigo.variables[int(varID)]
						except:
								self.ML.myLog( text =" error; varibale with indigoID = "+ str(varID) +" does not exist, removing from tracking")
								delList.append(varID)
								continue
							   
					sss =self.varList[varID]
					if True:
						variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(var)
						
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = "variName: "+variName+ " ... lastCheck+checkFrequency: "+str(sss["lastCheck"])+ " + "+str(sss["checkFrequency"])+" < " +str(now)+"now", mType="secs since.. Logic" )
						if self.subscribe != "subscribe":
							if not( (sss["lastCheck"] + sss["checkFrequency"]) < now or value != sss["lastValue"]) : continue
						elif  not ( (sss["lastCheck"] + sss["checkFrequency"]) < now ) : continue
						
						sss["lastCheck"] = now
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = " ...  data : "+unicode(sss), mType="secs since.. Logic")
						

						if value != sss["lastValue"]:
							indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
							indigo.variable.updateValue(variName,"0")
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss["lastChange"]))) )
							sss["lastValue"]		= value
							sss["previousChange"]	= sss["lastChange"]
							sss["lastChange"]		= now
						elif (sss["lastChange"] + sss["checkFrequency"]) < now :
							indigo.variable.updateValue(variName, str(int(now-float(sss["lastChange"]))) )
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss["previousChange"]))) )
				for varID in delList:
					del self.varList[varID]

				self.sleep(self.loopTest)
				if datetime.datetime.now().hour != lastVcheckHour:
					VS.versionCheck(self.pluginId,self.pluginVersion,indigo,13,25,printToLog="log")
					lastVcheckHour = datetime.datetime.now().hour
				
			self.stopConcurrentCounter = 1
			serverPlugin = indigo.server.getPlugin(self.pluginId)
			serverPlugin.restart(waitUntilDone=False)
			self.sleep(1)
		except	Exception, e:
			if len(unicode(e)) > 5:
				self.ML.myLog( text ="error in Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
		self.pluginPrefs["devList"] =json.dumps(self.devList)
		self.pluginPrefs["varList"] =json.dumps(self.varList)
		self.quitNow ==""
		return



