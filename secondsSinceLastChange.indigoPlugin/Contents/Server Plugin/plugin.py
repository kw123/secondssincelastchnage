#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# seconds since last change Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, pwd
import datetime, time
import json
from time import gmtime, strftime, localtime
import copy
import logging
import platform



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

_emptyDev={"states":{}}
_emptyState={"lastChange":0,"lastCheck":0,"checkFrequency":0,"lastValue":"", "'checkFrequency": 60, "previousChange":0}

_emptyVar={"lastChange":0,"lastCheck":0,"checkFrequency":0,"lastValue":"", "'checkFrequency": 60, "previousChange":0}


################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.pathToPlugin = os.getcwd() + "/"
		## = /Library/Application Support/Perceptive Automation/Indigo 6/Plugins/piBeacon.indigoPlugin/Contents/Server Plugin
		self.pluginShortName 			= "secondsSinceLastChange"
		self.quitNOW					= ""
###############  common for all plugins ############
		self.getInstallFolderPath		= indigo.server.getInstallFolderPath()+"/"
		self.indigoPath					= indigo.server.getInstallFolderPath()+"/"
		self.indigoRootPath 			= indigo.server.getInstallFolderPath().split("Indigo")[0]
		self.pathToPlugin 				= self.completePath(os.getcwd())

		major, minor, release 			= map(int, indigo.server.version.split("."))
		self.indigoVersion 				= float(major)+float(minor)/10.
		self.indigoRelease 				= release

		self.pluginVersion				= pluginVersion
		self.pluginId					= pluginId
		self.pluginName					= pluginId.split(".")[-1]
		self.myPID						= os.getpid()
		self.pluginState				= "init"

		self.myPID 						= os.getpid()
		self.MACuserName				= pwd.getpwuid(os.getuid())[0]

		self.MAChome					= os.path.expanduser("~")
		self.userIndigoDir				= self.MAChome + "/indigo/"
		self.indigoPreferencesPluginDir = self.getInstallFolderPath+"Preferences/Plugins/"+self.pluginId+"/"
		self.indigoPluginDirOld			= self.userIndigoDir + self.pluginShortName+"/"
		self.PluginLogFile				= indigo.server.getLogsFolderPath(pluginId=self.pluginId) +"/plugin.log"

		formats=	{   logging.THREADDEBUG: "%(asctime)s %(msg)s",
						logging.DEBUG:       "%(asctime)s %(msg)s",
						logging.INFO:        "%(asctime)s %(msg)s",
						logging.WARNING:     "%(asctime)s %(msg)s",
						logging.ERROR:       "%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s",
						logging.CRITICAL:    "%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s" }

		date_Format = { logging.THREADDEBUG: "%Y-%m-%d %H:%M:%S",		# 5
						logging.DEBUG:       "%Y-%m-%d %H:%M:%S",		# 10
						logging.INFO:        "%Y-%m-%d %H:%M:%S",		# 20
						logging.WARNING:     "%Y-%m-%d %H:%M:%S",		# 30
						logging.ERROR:       "%Y-%m-%d %H:%M:%S",		# 40
						logging.CRITICAL:    "%Y-%m-%d %H:%M:%S" }		# 50
		formatter = LevelFormatter(fmt="%(msg)s", datefmt="%Y-%m-%d %H:%M:%S", level_fmts=formats, level_date=date_Format)

		self.plugin_file_handler.setFormatter(formatter)
		self.indiLOG = logging.getLogger("Plugin")  
		self.indiLOG.setLevel(logging.THREADDEBUG)

		self.indigo_log_handler.setLevel(logging.INFO)

		self.indiLOG.log(20,"initializing  ...")
		self.indiLOG.log(20,"path To files:          =================")
		self.indiLOG.log(10,"indigo                  {}".format(self.indigoRootPath))
		self.indiLOG.log(10,"installFolder           {}".format(self.indigoPath))
		self.indiLOG.log(10,"plugin.py               {}".format(self.pathToPlugin))
		self.indiLOG.log(10,"indigo                  {}".format(self.indigoRootPath))
		self.indiLOG.log(20,"detailed logging        {}".format(self.PluginLogFile))
		self.indiLOG.log(20,"testing logging levels, for info only: ")
		self.indiLOG.log( 0,"logger  enabled for     0 ==> TEST ONLY ")
		self.indiLOG.log( 5,"logger  enabled for     THREADDEBUG    ==> TEST ONLY ")
		self.indiLOG.log(10,"logger  enabled for     DEBUG          ==> TEST ONLY ")
		self.indiLOG.log(20,"logger  enabled for     INFO           ==> TEST ONLY ")
		self.indiLOG.log(30,"logger  enabled for     WARNING        ==> TEST ONLY ")
		self.indiLOG.log(40,"logger  enabled for     ERROR          ==> TEST ONLY ")
		self.indiLOG.log(50,"logger  enabled for     CRITICAL       ==> TEST ONLY ")
		self.indiLOG.log(10,"Plugin short Name       {}".format(self.pluginShortName))
		self.indiLOG.log(10,"my PID                  {}".format(self.myPID))	 
		self.indiLOG.log(10,"Achitecture             {}".format(platform.platform()))	 
		self.indiLOG.log(10,"OS                      {}".format(platform.mac_ver()[0]))	 
		self.indiLOG.log(10,"indigo V                {}".format(indigo.server.version))	 


	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)


	########################################
	def startup(self):


		self.debugOptions = ["Logic","all","Config","Subscribe","Special"]

		major, minor, release = map(int, indigo.server.version.split("."))


		
		self.loopTest				= float(self.pluginPrefs.get("loopTest",2.0))
		self.subscribe				= self.pluginPrefs.get("subscribe","loop")
		self.variFolderName			= self.pluginPrefs.get("variFolderName","Seconds")
		self.extraUnderscore		= self.pluginPrefs.get("variFolderName","1")
		self.devList				= json.loads(self.pluginPrefs.get("devList","{}"))
		self.varList				= json.loads(self.pluginPrefs.get("varList","{}"))

		self.saveNow				= False
		self.devID					= 0
		self.quitNow				= "" # set to !="" when plugin should exit ie to restart, needed for subscription -> loop model
		self.stopConcurrentCounter 	= 0


		if not os.path.exists(self.indigoPreferencesPluginDir):
			os.mkdir(self.indigoPreferencesPluginDir)
			if not os.path.exists(self.indigoPreferencesPluginDir):
				self.errorLog("error creating the plugin data dir did not work, can not create: {}".format(self.indigoPreferencesPluginDir))
				self.sleep(1000)
				exit()

		self.debugLevel = []
		for d in self.debugOptions:
			if self.pluginPrefs.get("debug"+d, False): self.debugLevel.append(d)

		

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
				self.varList[dd]["lastValue"] = ""

		
		
		self.printConfigCALLBACK()
		self.pluginPrefs["devList"] = json.dumps(self.devList)
		self.pluginPrefs["varList"] = json.dumps(self.varList)
		
		return


	########################################
	def deviceStartComm(self, dev):
		return
	

	########################################
	def deviceStopComm(self, dev):
		return


	########################################
	def stopConcurrentThread(self):
		self.stopConcurrentCounter +=1
		self.indiLOG.log(30,"stopConcurrentThread called {}".format(self.stopConcurrentCounter))
		if self.stopConcurrentCounter ==1:
			self.stopThread = True



	########################################
	def variableUpdated(self, origVar, newVar):
		try:
			if self.subscribe !="subscribe": return
			varstr = "{}".format(origVar.id)
			if varstr not in self.varList: return

			now=time.time()
			sss =self.varList[varstr]
			varName= origVar.name
			if self.decideMyLog("Subscribe"): self.indiLOG.log(20,"Subscribe checking variable: {}".format(varName))

			if origVar.value != newVar.value: 
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(indigo.variables[origVar.id])

				if self.decideMyLog("Subscribe"): self.indiLOG.log(20,"Subscribe .. changed from:{};  to:{};  secs_since last change: {}".format(origVar.value, newVar.value, int(now - sss["lastChange"])) )

				indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
				indigo.variable.updateValue(variNamePrevious, "{}".format(int(now - sss["lastChange"])))
				indigo.variable.updateValue(variName,"0")
				sss["lastValue"]		= newVar.value
				sss["previousChange"]	= sss["lastChange"]
				sss["lastChange"]		= now
				sss["lastCheck"] 		= now
		except	Exception:
			self.logger.error("", exc_info=True)


	########################################
	def deviceUpdated(self, origDev, newDev):
		try:
			if self.subscribe != "subscribe": return
			devstr = "{}".format(origDev.id)
			if devstr not in self.devList: return

			now=time.time()
			ddd =self.devList[devstr]
			devName= origDev.name
			if self.decideMyLog("Subscribe"): self.indiLOG.log(20,"Subscribe checking device :\"{}\" .. ".format(devName) )
			dev = indigo.devices[origDev.id]

			for state in self.devList[devstr]["states"]:
				if state not in newDev.states: continue
				if origDev.states[state] == newDev.states[state]: continue
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
				sss = ddd["states"][state]
				if self.decideMyLog("Subscribe"): self.indiLOG.log(20,"...  state:\"{}\"  changed from:\"{}\", to:\"{}\", secs_since last change: {}".format(state, origDev.states[state],  newDev.states[state], int(now - sss["lastChange"])))

				indigo.variable.updateValue(variNamePrevious, "{}".format(int(now - sss["lastChange"])))
				indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"])
				indigo.variable.updateValue(variName,"0")
				sss["lastValue"]		= "{}".format(newDev.states[state])
				sss["previousChange"]	= sss["lastChange"]
				sss["lastChange"]		= now
				sss["lastCheck"]		= now
		except	Exception:
			self.logger.error("", exc_info=True)

		return
	

####-----------------  set the geneeral config parameters---------
	def validatePrefsConfigUi(self, valuesDict):

		self.variFolderName		= valuesDict["variFolderName"]
		self.loopTest			= float(valuesDict["loopTest"])

		try:
			indigo.variables.folder.create(self.variFolderName)
		except:
			pass

		self.debugLevel = []
		for d in self.debugOptions:
			if valuesDict[ "debug"+d] : self.debugLevel.append(d)

		self.extraUnderscore = valuesDict.get("extraUnderscore","1")

		xx = valuesDict["subscribe"]
		if xx != self.subscribe:
			self.subscribe = xx
			if xx == "subscribe":
				indigo.devices.subscribeToChanges()
				indigo.variables.subscribeToChanges()

			else:
				self.indiLOG.log(30,"restart plugin needed to UN-subscribe to changes")
				self.quitNow = "yes" # need to restart

		return True, valuesDict


	########################################
	def dummyCALLBACK(self):
		
		return


	########################################
	def printConfigCALLBACK(self,devstr=""):
		try:
			if len(self.devList)> 0:
				self.indiLOG.log(20,"Configuration")
				#							  	  012345678901234567890123456789012345678901234 0123456789012345678901234
				self.indiLOG.log(20,"DevID        Dev-Name------------------------------------- --------------------State  Data----------")
				for devid in self.devList:
					if devid == devstr or devstr == "":
						for state in self.devList[devid]["states"]:
							#self.indiLOG.log(20,"{:12} {:20} {:25}{:20}  {:20}".format(devid, indigo.devices[int(devid)].name, state, self.devList[devid]["states"][state]))
							self.indiLOG.log(20,"{:12} {:45} {:>25} {:}".format(devid, indigo.devices[int(devid)].name, state, self.devList[devid]["states"][state]))
			else:
							self.indiLOG.log(20,"no devices defined " )


			if len(self.varList)> 0:
				self.indiLOG.log(20,"Configuration")
				#								0123456789012345678901234678901234 0123456789012345678901234
				self.indiLOG.log(20,"VarID     Var-Name-------------------------- Data-------------")
				for varid in self.varList:
					self.indiLOG.log(20,"{:12} {:35} {}".format(varid, indigo.variables[int(varid)].name, self.varList[varid]))
			else:
					self.indiLOG.log(20,"no variables defined " )
		except	Exception:
			self.logger.error("", exc_info=True)
		
		return


	########################################
	def pickDeviceCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.decideMyLog("Config"): self.indiLOG.log(20,"secs since..Config  {}".format(valuesDict))
		self.devID= int(valuesDict["device"])
		return valuesDict


	########################################
	def filterStates(self,filter="",valuesDict="",typeId=""):				# Select only device/properties that are supported
	
		if self.devID == 0: return [(0,0)]
		retList=[]
		dev =  indigo.devices[self.devID]
		devstr = "{}".format(dev.id)
		if devstr in self.devList: check = True
		else:                      check = False
		for state in dev.states.keys():
			if check and state in self.devList[devstr]["states"]:
				retList.append((state, "remove: "+state))
			else:
				retList.append((state, "add: "+state))
		return retList


	########################################
	def pickVariableCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.decideMyLog("Config"): self.indiLOG.log(20,"secs since..Config  {}".format(valuesDict))
		self.varID= int(valuesDict["variable"])
		return valuesDict


	########################################
	def buttonAddCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict["device"])]
		devstr= "{}".format(dev.id)
		if devstr not in self.devList:
			self.devList[devstr]				= copy.deepcopy(_emptyDev)
		
		state = valuesDict["state"]
		if	state not in self.devList[devstr]["states"]:
			self.devList[devstr]["states"][state]	=copy.deepcopy(_emptyState)
		
		self.devList[devstr]["states"][state]["checkFrequency"] = int(valuesDict["checkFrequency"])
		self.devList[devstr]["states"][state]["lastChange"]		= time.time()
		self.devList[devstr]["states"][state]["lastCheck"]		= 0
		self.saveNow = True
		self.createOrConfirmVariablesForDevice(indigo.devices[dev.id],state)
		
		self.printConfigCALLBACK(devstr=devstr)

		return valuesDict

		
	########################################
	def buttonRemoveCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict["device"])]
		devstr= "{}".format(dev.id)
		if devstr in self.devList:
			state = valuesDict["state"]
			if	state in self.devList[devstr]["states"]:
				del self.devList[devstr]["states"][state]
			if len(self.devList[devstr])==0:
				del self.devList[devstr]
			
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def buttonAddVARCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		var=indigo.variables[int(valuesDict["variable"])]
		varstr= "{}".format(dev.id)
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
		varstr= "{}".format(var.id)
		if varstr in self.varList:
			del self.varList[varstr]
	
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def createOrConfirmVariablesForDevice(self,dev,state):
		if self.extraUnderscore == "2":
			name					= dev.name.strip().replace(" ","_")+"__"+state.replace(" ","_")
			variName				= name+"__seconds_since_change"
			variNamePrevious		= name+"__seconds_previous_change"
			variNamePreviousValue	= name+"__previous_value"
		else:
			name					= dev.name.strip().replace(" ","_")+"_"+state.replace(" ","_")
			variName				= name+"_seconds_since_change"
			variNamePrevious		= name+"_seconds_previous_change"
			variNamePreviousValue	= name+"_previous_value"

		try: 	indigo.variable.create(variName,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePrevious,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePreviousValue,"{}".format(dev.states[state]),self.variFolderName)
		except: pass
		try:	newValue = "{}".format(dev.states[state])
		except: pass
		#self.indiLOG.log(20,"{}-{} gives:{} ..\n states:{}".format(dev.id, state, newValue, dev.states))
		
		return variName, variNamePrevious, variNamePreviousValue, newValue
		
	########################################
	def createOrConfirmVariablesForVariable(self,var):
		try:
			if self.extraUnderscore == "2":
				name					= var.name.strip().replace(" ","_")
				variName				= name+"__seconds_since_change"
				variNamePrevious		= name+"__seconds_previous_change"
				variNamePreviousValue	= name+"__previous_value"
			else:
				name					= var.name.strip().replace(" ","_")
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
		except	Exception:
			self.logger.error("", exc_info=True)
		return "","","",""

	########### main loop -- start #########
	########################################
	def runConcurrentThread(self):

		if self.subscribe =="subscribe":
			indigo.devices.subscribeToChanges()
			indigo.variables.subscribeToChanges()

		lastVcheckHour = -1
		lastSave=time.time()
		try:
			while self.quitNow == "":
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
						except Exception as e:
						   if "{}".format(e).find("timeout") >-1: self.sleep(5)
						try:
							dev = indigo.devices[int(devID)]
						except:
								self.indiLOG.log(20," error; device with indigoID = {} does not exist, removing from tracking".format(devID))
								delList.append(devID)
								continue
							   
					ddd =self.devList[devID]
					for state in ddd["states"]:
						sss = ddd["states"][state]
						if (sss["lastCheck"] + sss["checkFrequency"]) > now: continue

						variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
						
						if self.decideMyLog("Logic"):self.indiLOG.log(20,"{}... check: {}, data:{}".format(dev.name, (sss["lastCheck"] + sss["checkFrequency"]) < now, ddd) )

						if value != sss["lastValue"]:
							indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
							indigo.variable.updateValue(variName,"0")
							indigo.variable.updateValue(variNamePrevious, "{}".format(int(now-float(sss["lastChange"]))) )
							sss["lastValue"]		= value
							sss["previousChange"]	= sss["lastChange"]
							sss["lastChange"]		= now
						else:
							indigo.variable.updateValue(variName, "{}".format(int(now-float(sss["lastChange"]))) )
							indigo.variable.updateValue(variNamePrevious, "{}".format(int(now-float(sss["previousChange"]))) )
						sss["lastCheck"] = now

				for devID in delList:
					del self.devList[devID]


				delList=[]	  
				for varID in self.varList:
					if int(varID) >0:
						try:
							var= indigo.variables[int(varID)]
						except Exception as e:
						   if "{}".format(e).find("timeout") >-1: self.sleep(5)
						try:
							var = indigo.variables[int(varID)]
						except:
								self.indiLOG.log(20," error; varibale with indigoID =  does not exist, removing from tracking".format(varID))
								delList.append(varID)
								continue
							   
					sss = self.varList[varID]
					if (sss["lastCheck"] + sss["checkFrequency"]) > now: continue
					variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(var)
					
					if self.decideMyLog("Logic"): self.indiLOG.log(20,"{} ... check: {}, data:{}".format(variName,(sss["lastCheck"] + sss["checkFrequency"]) < now, sss) )

					if value != sss["lastValue"]:
						indigo.variable.updateValue(variNamePreviousValue, sss["lastValue"] )
						indigo.variable.updateValue(variName,"0")
						indigo.variable.updateValue(variNamePrevious, "{}".format(int(now-float(sss["lastChange"]))) )
						sss["lastValue"]		= value
						sss["previousChange"]	= sss["lastChange"]
						sss["lastChange"]		= now
					else:
						indigo.variable.updateValue(variName, "{}".format(int(now-float(sss["lastChange"]))) )
						indigo.variable.updateValue(variNamePrevious, "{}".format(int(now-float(sss["previousChange"]))) )
					sss["lastCheck"] = now

				for varID in delList:
					del self.varList[varID]

				try:
					lastCheck = time.time()
					for ii in range(1000):
						if time.time() - lastCheck >= self.loopTest: break
						if self.quitNow != "": 						 break
						self.sleep(1)
				except: break

			
			self.stopConcurrentCounter = 1
			serverPlugin = indigo.server.getPlugin(self.pluginId)
			serverPlugin.restart(waitUntilDone=False)
		except:
			pass

		self.pluginPrefs["devList"] =json.dumps(self.devList)
		self.pluginPrefs["varList"] =json.dumps(self.varList)
		self.quitNow = ""
		return

####-----------------	 ---------
	def decideMyLog(self, msgLevel):
		try:
			if msgLevel	 == "all" or "all" in self.debugLevel:	 	return True
			if msgLevel	 == ""	 and  "all" not in self.debugLevel: return False
			if msgLevel in self.debugLevel:							return True
		except	Exception:
			self.logger.error("", exc_info=True)
		if True:													return False

####-----------------	 ---------
	def completePath(self,inPath):
		if len(inPath) == 0: return ""
		if inPath == " ":	 return ""
		if inPath[-1] != "/": inPath +="/"
		return inPath

####-----------------  valiable formatter for differnt log levels ---------
# call with: 
# formatter = LevelFormatter(fmt='<default log format>', level_fmts={logging.INFO: '<format string for info>'})
# handler.setFormatter(formatter)
class LevelFormatter(logging.Formatter):
	def __init__(self, fmt=None, datefmt=None, level_fmts={}, level_date={}):
		self._level_formatters = {}
		self._level_date_format = {}
		for level, format in level_fmts.items():
			# Could optionally support level names too
			self._level_formatters[level] = logging.Formatter(fmt=format, datefmt=level_date[level])
		# self._fmt will be the default format
		super(LevelFormatter, self).__init__(fmt=fmt, datefmt=datefmt)
		return

	def format(self, record):
		if record.levelno in self._level_formatters:
			return self._level_formatters[record.levelno].format(record)

		return super(LevelFormatter, self).format(record)



