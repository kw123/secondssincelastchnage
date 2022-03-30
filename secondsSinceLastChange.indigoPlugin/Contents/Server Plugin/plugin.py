#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# seconds since last change Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, pwd
import datetime, time
import simplejson as json
from time import gmtime, strftime, localtime
import copy
import myLogPgms.myLogPgms 

try:
	unicode("x")
except:
	unicode = str
import traceback



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


_emptyDev={u"states":{}}
_emptyState={"lastChange":0,u"lastCheck":0,u"checkFrequency":0,u"lastValue":"", u"'checkFrequency": 60, u"previousChange":0}

_emptyVar={u"lastChange":0,u"lastCheck":0,u"checkFrequency":0,u"lastValue":"", u"'checkFrequency": 60, u"previousChange":0}


################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.pathToPlugin = os.getcwd() + "/"
		## = /Library/Application Support/Perceptive Automation/Indigo 6/Plugins/piBeacon.indigoPlugin/Contents/Server Plugin
		p = max(0, self.pathToPlugin.lower().find(u"/plugins/")) + 1
		self.indigoPath = self.pathToPlugin[:p]
		self.pluginState		= u"init"
		self.pluginShortName 	= u"secondsSinceLastChange"
		self.pluginVersion		= pluginVersion
		self.pluginId			= pluginId
	
	
	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
	
	########################################
	def startup(self):


		self.debugOptions = [u"Logic",u"all",u"Config",u"Subscribe",u"Special"]

		major, minor, release = map(int, indigo.server.version.split("."))

		if  major < 7:
			indigo.server.log(u"need indigo version >7; running on : >>"+unicode(indigo.server.version)+u"<<")
			self.sleep(1000)
			exit()

		
		self.loopTest				= float(self.pluginPrefs.get(u"loopTest",2.0))
		self.subscribe				= self.pluginPrefs.get(u"subscribe","loop")
		self.variFolderName			= self.pluginPrefs.get(u"variFolderName","Seconds")
		self.devList				= json.loads(self.pluginPrefs.get(u"devList",u"{}"))
		self.varList				= json.loads(self.pluginPrefs.get(u"varList",u"{}"))

		self.saveNow			= False
		self.devID				= 0
		self.quitNow			= "" # set to !="" when plugin should exit ie to restart, needed for subscription -> loop model
		self.stopConcurrentCounter = 0


		self.MACuserName   = pwd.getpwuid(os.getuid())[0]
		self.MAChome	   = os.path.expanduser(u"~")
		self.indigoHomeDir = self.MAChome+u"/indigo/" #	this is the data directory

		self.indigoConfigDir	 = self.indigoHomeDir + self.pluginShortName+u"/"

		self.pythonPath					= u"/usr/bin/python2.6"
		if os.path.isfile(u"/usr/bin/python2.7"):
			self.pythonPath				= u"/usr/bin/python2.7"


		if not os.path.exists(self.indigoHomeDir):
			os.mkdir(self.indigoHomeDir)

		if not os.path.exists(self.indigoConfigDir):
			os.mkdir(self.indigoConfigDir)
			if not os.path.exists(self.indigoConfigDir):
				self.errorLog(u"error creating the plugin data dir did not work, can not create: "+ self.indigoConfigDir)
				self.sleep(1000)
				exit()

		self.debugLevel = []
		for d in self.debugOptions:
			if self.pluginPrefs.get(u"debug"+d, False): self.debugLevel.append(d)

		self.ML = myLogPgms.myLogPgms.MLX()
		self.setLogfile(unicode(self.pluginPrefs.get(u"logFileActive2", u"standard")))
		

		for dd in self.devList:
			dev = indigo.devices[int(dd)]
			for ss in self.devList[dd][u"states"]:
				self.createOrConfirmVariablesForDevice(dev,ss)
				if u"previousChange" not in self.devList[dd][u"states"][ss]:
					self.devList[dd][u"states"][ss][u"previousChange"] =0

		for dd in self.varList:
			var = indigo.variables[int(dd)]
			self.createOrConfirmVariablesForVariable(var)
			if u"lastValue" not in self.varList[dd]:
				self.varList[dd][u"lastValue"] = u"-1"

		
		
		self.printConfigCALLBACK()
		self.pluginPrefs[u"devList"] = json.dumps(self.devList)
		self.pluginPrefs[u"varList"] = json.dumps(self.varList)
		
		return


	####-----------------	 ---------
	def setLogfile(self,lgFile):
		self.logFileActive = lgFile
		if   self.logFileActive == u"standard":	self.logFile = ""
		elif self.logFileActive == u"indigo":	self.logFile = self.indigoPath.split(u"Plugins/")[0]+u"Logs/"+self.pluginId+u"/plugin.log"
		else:									self.logFile = self.indigoConfigDir + self.pluginShortName+".log"
		self.ML.myLogSet(debugLevel = self.debugLevel ,logFileActive=self.logFileActive, logFile = self.logFile, pluginSelf=self)

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
			if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = u"checking variable: "+varName, mType=u"secs since..Subscribe" )

			if origVar.value != newVar.value: 
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(indigo.variables[origVar.id])

				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = u" .. changed from:"+origVar.value+u";  to:"+ newVar.value+u";  secs_since last change: "+str(int(now - sss[u"lastChange"])), mType=u"secs since..Subscribe" )

				indigo.variable.updateValue(variNamePreviousValue, sss[u"lastValue"] )
				indigo.variable.updateValue(variNamePrevious, str(int(now - sss[u"lastChange"])))
				indigo.variable.updateValue(variName,u"0")
				sss[u"lastValue"]		= newVar.value
				sss[u"previousChange"]	= sss[u"lastChange"]
				sss[u"lastChange"]		= now
				sss[u"lastCheck"] 		= now
		except	Exception as e:
			self.exceptionHandler(40,e)

	

	########################################
	def deviceUpdated(self, origDev, newDev):
		try:
			if self.subscribe != u"subscribe": return
			devstr = str(origDev.id)
			if devstr not in self.devList: return

			now=time.time()
			ddd =self.devList[devstr]
			devName= origDev.name
			if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = u"checking device :"+devName, mType=u"secs since..Subscribe" )
			dev = indigo.devices[origDev.id]

			for state in self.devList[devstr][u"states"]:
				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = (u"   state: "+state).ljust(25)+u";  old value:"+ unicode(origDev.states[state]), mType=u"secs since..Subscribe" )
				if state not in newDev.states: continue
				if origDev.states[state] == newDev.states[state]: continue
				# change happend for dev/state we asked for, now rest conter ...
				variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
				sss = ddd[u"states"][state]
				if self.ML.decideMyLog(u"Subscribe"): self.ML.myLog( text = u"                           changed to:".ljust(38)+ unicode(newDev.states[state])+u";  secs_since last change: "+str(int(now - sss[u"lastChange"])), mType=u"secs since..Subscribe" )

				indigo.variable.updateValue(variNamePrevious, str(int(now - sss[u"lastChange"])))
				indigo.variable.updateValue(variNamePreviousValue, sss[u"lastValue"])
				indigo.variable.updateValue(variName,u"0")
				sss[u"lastValue"]		= unicode(newDev.states[state])
				sss[u"previousChange"]	= sss[u"lastChange"]
				sss[u"lastChange"]		= now
				sss[u"lastCheck"]		= now
		except	Exception as e:
			self.exceptionHandler(40,e)

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
				self.quitNow = u"yes" # need to restart
				self.ML.myLog( text = u"restart plugin needed to UNsubscribe to changes")

		self.subscribe = xx

		try:
			indigo.variables.folder.create(self.variFolderName)
		except:
			pass

		self.debugLevel = []
		for d in self.debugOptions:
			if valuesDict[ u"debug"+d] : self.debugLevel.append(d)
				

		self.setLogfile(valuesDict[u"logFileActive2"])

		return True, valuesDict


	########################################
	def dummyCALLBACK(self):
		
		return
	########################################
	def printConfigCALLBACK(self,devstr=""):
		if len(self.devList)> 0:
			self.ML.myLog( text =u"Configuration")
			self.ML.myLog( text =u"Dev-Name----------       ---------------State  Data----------", mType=u"DevID")
			for devid in self.devList:
				if devid == devstr or devstr=="":
					for state in self.devList[devid][u"states"]:
						self.ML.myLog( text =  indigo.devices[int(devid)].name.ljust(25) +state.rjust(20)+u"  "+ unicode(self.devList[devid][u"states"][state]), mType=devid.ljust(10) )
		else:
						self.ML.myLog( text =  u"no devices defined " )


		if len(self.varList)> 0:
			self.ML.myLog( text =u"Configuration")
			self.ML.myLog( text =u"Var-Name----------".ljust(25)+"  Data-------------", mType=u"VarID")
			for varid in self.varList:
				self.ML.myLog( text =  indigo.variables[int(varid)].name.ljust(25)+u"  "+ unicode(self.varList[varid]), mType=varid.ljust(10))
		else:
				self.ML.myLog( text =  u"no variables defined " )
		
		return
	########################################
	def pickDeviceCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.ML.decideMyLog(u"Config"): self.ML.myLog( text = unicode(valuesDict), mType=u"secs since..Config")
		self.devID= int(valuesDict[u"device"])
		return valuesDict

	########################################
	def filterStates(self,filter="",valuesDict="",typeId=""):				# Select only device/properties that are supported
	
		if self.devID ==0: return [(0,0)]
		retList=[]
		dev =  indigo.devices[self.devID]
		devstr = str(dev.id)
		if devstr in self.devList: check = True
		else:                      check = False
		for state in dev.states.keys():
			if check and state in self.devList[devstr][u"states"]:
				retList.append((state, u"remove: "+state))
			else:
				retList.append((state, u"add: "+state))
		return retList

	########################################
	def pickVariableCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		if self.ML.decideMyLog(u"Config"): self.ML.myLog( text = unicode(valuesDict), mType=u"secs since..Config")
		self.varID= int(valuesDict[u"variable"])
		return valuesDict



	########################################
	def buttonAddCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict[u"device"])]
		devstr= str(dev.id)
		if devstr not in self.devList:
			self.devList[devstr]				= copy.deepcopy(_emptyDev)
		
		state = valuesDict[u"state"]
		if	state not in self.devList[devstr][u"states"]:
			self.devList[devstr][u"states"][state]	=copy.deepcopy(_emptyState)
		
		self.devList[devstr][u"states"][state][u"checkFrequency"] = int(valuesDict[u"checkFrequency"])
		self.devList[devstr][u"states"][state][u"lastChange"]		= time.time()
		self.devList[devstr][u"states"][state][u"lastCheck"]		= 0
		self.saveNow = True
		self.createOrConfirmVariablesForDevice(indigo.devices[dev.id],state)
		
		self.printConfigCALLBACK(devstr=devstr)

		return valuesDict

		
	########################################
	def buttonRemoveCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		dev=indigo.devices[int(valuesDict[u"device"])]
		devstr= str(dev.id)
		if devstr in self.devList:
			state = valuesDict[u"state"]
			if	state in self.devList[devstr][u"states"]:
				del self.devList[devstr][u"states"][state]
			if len(self.devList[devstr])==0:
				del self.devList[devstr]
			
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def buttonAddVARCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		var=indigo.variables[int(valuesDict[u"variable"])]
		varstr= str(var.id)
		if varstr not in self.varList:
			self.varList[varstr]				= copy.deepcopy(_emptyVar)
		
		self.varList[varstr][u"checkFrequency"]	= int(valuesDict[u"checkFrequency"])
		self.varList[varstr][u"lastChange"]		= time.time()
		self.varList[varstr][u"lastCheck"]		= 0

		self.saveNow=True
		self.createOrConfirmVariablesForVariable(indigo.variables[var.id])
		self.printConfigCALLBACK(devstr=varstr)

		return valuesDict

	########################################
	def buttonRemoveVARCALLBACK(self,valuesDict="",typeId=""):				# Select only device/properties that are supported
		var=indigo.variables[int(valuesDict[u"variable"])]
		varstr= str(var.id)
		if varstr in self.varList:
			del self.varList[varstr]
	
		self.printConfigCALLBACK()

		return valuesDict

	########################################
	def createOrConfirmVariablesForDevice(self,dev,state):
		name					= dev.name.replace(u" ",u"_")+u"_"+state.replace(u" ",u"_")
		variName				= name+u"_seconds_since_change"
		variNamePrevious		= name+u"_seconds_previous_change"
		variNamePreviousValue	= name+u"_previous_value"
		try: 	indigo.variable.create(variName,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePrevious,"0",self.variFolderName)
		except: pass
		try: 	indigo.variable.create(variNamePreviousValue,str(dev.states[state]),self.variFolderName)
		except: pass
		return variName, variNamePrevious, variNamePreviousValue, unicode(dev.states[state])
		
	########################################
	def createOrConfirmVariablesForVariable(self,var):
		try:
			name					= var.name
			variName				= name+u"_seconds_since_change"
			variNamePrevious		= name+u"_seconds_previous_change"
			variNamePreviousValue	= name+u"_previous_value"
			try: 	indigo.variable.create(variName,u"0",self.variFolderName)
			except: pass
			try: 	indigo.variable.create(variNamePrevious,u"0",self.variFolderName)
			except: pass
			try: 	indigo.variable.create(variNamePreviousValue,var.value,self.variFolderName)
			except: pass
			return variName, variNamePrevious, variNamePreviousValue, var.value
		except	Exception as e:
			self.exceptionHandler(40,e)
		return "","","",""

	########### main loop -- start #########
	########################################
	def runConcurrentThread(self):

		if self.subscribe ==u"subscribe":
			indigo.devices.subscribeToChanges()
			indigo.variables.subscribeToChanges()

		lastVcheckHour = -1
		lastSave=time.time()
		try:
			while self.quitNow =="":
				now = time.time()
				if self.saveNow or lastSave +60 < now:
					self.pluginPrefs[u"devList"] =json.dumps(self.devList)
					self.pluginPrefs[u"varList"] =json.dumps(self.varList)
					self.saveNow=False
				delList=[]	  
				for devID in self.devList:
					if int(devID) >0:
						try:
							dev= indigo.devices[int(devID)]
						except Exception as e:
						   if unicode(e).find(u"timeout") >-1: self.sleep(5)
						try:
							dev = indigo.devices[int(devID)]
						except:
								self.ML.myLog( text =u" error; device with indigoID = "+ str(devID) +u" does not exist, removing from tracking")
								delList.append(devID)
								continue
							   
					ddd =self.devList[devID]
					for state in ddd[u"states"]:
						sss = ddd[u"states"][state]
						variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForDevice(dev,state)
						
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = u"name: "+dev.name+ u"... lastCheck+checkFrequency: "+str(sss[u"lastCheck"])+ u" + "+str(sss[u"checkFrequency"])+u" < " +str(now)+u"now", mType=u"secs since.. Logic" )
						if self.subscribe != u"subscribe":
							if not( (sss[u"lastCheck"] + sss[u"checkFrequency"]) < now or value != sss[u"lastValue"]) : continue
						elif  not ( (sss[u"lastCheck"] + sss[u"checkFrequency"]) < now ) : continue
						
						sss[u"lastCheck"] = now
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = u" ... data: "+unicode(ddd))
						

						if value != sss[u"lastValue"]:
							indigo.variable.updateValue(variNamePreviousValue, sss[u"lastValue"] )
							indigo.variable.updateValue(variName,u"0")
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss[u"lastChange"]))) )
							sss[u"lastValue"]		= value
							sss[u"previousChange"]	= sss[u"lastChange"]
							sss[u"lastChange"]		= now
						elif (sss[u"lastChange"] + sss[u"checkFrequency"]) < now :
							indigo.variable.updateValue(variName, str(int(now-float(sss[u"lastChange"]))) )
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss[u"previousChange"]))) )
				for devID in delList:
					del self.devList[devID]


				delList=[]	  
				for varID in self.varList:
					if int(varID) >0:
						try:
							var= indigo.variables[int(varID)]
						except Exception as e:
						   if unicode(e).find(u"timeout") >-1: self.sleep(5)
						try:
							var = indigo.variables[int(varID)]
						except:
								self.exceptionHandler(40,e)
								delList.append(varID)
								continue
							   
					sss =self.varList[varID]
					if True:
						variName, variNamePrevious, variNamePreviousValue, value = self.createOrConfirmVariablesForVariable(var)
						
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = u"variName: "+variName+ u" ... lastCheck+checkFrequency: "+str(sss[u"lastCheck"])+ u" + "+str(sss[u"checkFrequency"])+u" < " +str(now)+u"now", mType=u"secs since.. Logic" )
						if self.subscribe != u"subscribe":
							if not( (sss[u"lastCheck"] + sss[u"checkFrequency"]) < now or value != sss[u"lastValue"]) : continue
						elif  not ( (sss[u"lastCheck"] + sss[u"checkFrequency"]) < now ) : continue
						
						sss[u"lastCheck"] = now
						if self.ML.decideMyLog(u"Logic"): self.ML.myLog( text = u" ...  data : "+unicode(sss), mType=u"secs since.. Logic")
						

						if value != sss[u"lastValue"]:
							indigo.variable.updateValue(variNamePreviousValue, sss[u"lastValue"] )
							indigo.variable.updateValue(variName,"0")
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss[u"lastChange"]))) )
							sss[u"lastValue"]		= value
							sss[u"previousChange"]	= sss[u"lastChange"]
							sss[u"lastChange"]		= now
						elif (sss[u"lastChange"] + sss[u"checkFrequency"]) < now :
							indigo.variable.updateValue(variName, str(int(now-float(sss[u"lastChange"]))) )
							indigo.variable.updateValue(variNamePrevious, str(int(now-float(sss[u"previousChange"]))) )
				for varID in delList:
					del self.varList[varID]

				self.sleep(self.loopTest)
				
			self.stopConcurrentCounter = 1
			serverPlugin = indigo.server.getPlugin(self.pluginId)
			serverPlugin.restart(waitUntilDone=False)
			self.sleep(1)
		except	Exception as e:
			self.exceptionHandler(40,e)
		self.pluginPrefs[u"devList"] =json.dumps(self.devList)
		self.pluginPrefs[u"varList"] =json.dumps(self.varList)
		self.quitNow ==""
		return




####-----------------  exception logging ---------
	def exceptionHandler(self, level, exception_error_message):

		try:
			try: 
				if u"{}".format(exception_error_message).find("None") >-1: return exception_error_message
			except: 
				pass

			filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
			#module = filename.split('/')
			log_message = "'{}'".format(exception_error_message )
			log_message +=  "\n{} @line {}: '{}'".format(method, line_number, statement)
			if level > 0:
				self.errorLog(log_message)
			return "'{}'".format(log_message )
		except Exception as e:
			indigo.server.log( "{}".format(e))





