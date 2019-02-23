#!/usr/bin/python 
import sys
import re
import copy
import logging

from jinja2 import Template

class StateMachine:

	def __init__(self):
		self.handlers = {}
		self.startState = None
		self.endStates = []

	def add_state(self, name, handler, end_state=0):
		name = name.upper()
		self.handlers[name] = handler
		if end_state:
			self.endStates.append(name)

	def set_start(self, name):
		self.startState = name.upper()

	def run(self, ctx, fileData):
		try:
			handler = self.handlers[self.startState]
		except:
			raise InitializationError("must call .set_start() before .run()")
		if not self.endStates:
			raise  InitializationError("at least one state must be an end_state")

		while True:
			(newState, fileData) = handler(ctx, fileData)
			ctx.current_lineNo += 1
			if newState.upper() in self.endStates:
				logging.info("Moving into end state %s", newState)
				break 
			else:
				logging.debug("Moving into %s", newState)
				ctx.current_state = newState
				handler = self.handlers[newState.upper()]

def startFSM(ctx, lines):
	logging.info('Entering %s', ctx.current_state)
	newState = "FETCH_REL_PLAT"
	return (newState, lines)

def fetchReleaseAndPlatform(ctx, lines):

	try:
	    line = lines[0]
	except IndexError:
		line = 'null'
		newState = "MISSING_REL_PLAT"
		return (newState, lines)
			
	platform = ""
	release  = ""

	z = re.search(r'ucs-(.*?)-huu-(.*?).iso', line)
	if z:

		platform = z.group(1)
		release = z.group(2)
		
		if release != "":
			if release in ctx.finalData.keys():
				if platform != "":
					if platform in ctx.finalData[release].keys():
						logging.critical('dropping & exiting since '+ i +' already processed\n')
						sys.exit()
					ctx.finalData[release][platform] = {}
				else:
					logging.critical("Error fetching 'Platform'")
					sys.exit()
			else:
				ctx.finalData[release] = {}
				if platform != "" :
					ctx.finalData[release][platform] = {}
				else:
					logging.critical("Error fetching 'Platform'")
					sys.exit()
					
		else:
		   logging.CRITICAL("Error fetching 'Release'")
		   sys.exit()

	if platform != "" and release != "":
		ctx.release = release
		ctx.platform = platform
		logging.info('RELEASE %s PLATFORM %s line %s', release, platform, ctx.current_lineNo)
		newState = "FETCH_COMPONENTS"
	else:
		newState = "FETCH_REL_PLAT"
	
	return (newState, lines[1:])

def fetchComponents(ctx, lines):
	try:
	    line = lines[0]
	except IndexError:
		line = 'null'
		newState = "EOF_IN_FETCH_COMPONENTS"
		return (newState, lines)

	componentName = ""
	newState = ctx.current_state

	z = re.search(r'^\s*(\b([A-Z-]+){1}\b)\s*$', line)
	if z:
		componentName = z.group(1)
		ctx.myDict["Component"].append(componentName)
		ctx.myDict[componentName] = []
		ctx.myDict[componentName].append(ctx.current_lineNo)
	
		if componentName != "":
			logging.info("COMPONENT: %s", componentName)
		else:
			assert (False),'Component Name absent'
		newState = 'FETCH_COMPONENTS_DATA'
		return (newState, lines[1:])
	
	if newState == 'FETCH_COMPONENTS_DATA':
			z = re.search(r'(^[\s]*[-]+[\s]*$)|(^[\s]*$|^HDD)', line)
			if z:
				logging.debug("Adding DUMMY1")
				componentName = "DUMMY1"
				ctx.myDict["Component"].append(componentName)
				ctx.myDict[componentName] = []
				ctx.myDict[componentName].append(ctx.current_lineNo)
				newState = 'FETCH_HDD_COMPONENT'

	return (newState, lines[1:])

def fetchHddComponent(ctx, lines):
	try:
	    line = lines[0]
	except IndexError:
		line = 'null'
		newState = 'EOF_IN_FETCH_HDD_COMPONENT'
		return (newState, lines)

	componentName = ""
	newState = ctx.current_state

	z = re.search(r'^[\s\t]*(HDD)[\s*\t*]+Model[\s\t]+Latest[\s\t]+([Ff][Ww]|firmware)', line, re.MULTILINE|re.IGNORECASE)
	if z:
		componentName = z.group(1)
		logging.info('Matched component %s lineNo=%s line=%s', componentName, ctx.current_lineNo, line)
		ctx.myDict["Component"].append(componentName)
		ctx.myDict[componentName] = []
		ctx.myDict[componentName].append(ctx.current_lineNo + 1)

		if componentName != "":
			logging.info("HDD COMPONENT: %s", componentName)
		else:
			assert (False),'HDD Component Name absent'

		newState = 'FETCH_HDD_COMPONENT_DATA'
		return (newState, lines[2:])

	if newState == 'FETCH_HDD_COMPONENT_DATA':
		z = re.search(r'(^[\s]*[-]+[\s]*$)|(^[\s]*$)', line)
		if z:
			logging.debug("Adding DUMMY2")
			componentName = "DUMMY2"
			ctx.myDict["Component"].append(componentName)
			ctx.myDict[componentName] = []
			ctx.myDict[componentName].append(ctx.current_lineNo + 1)
			newState = 'END'

	return (newState, lines[1:])

def addDummyMarkerAfterHdd(ctx, lines):

	logging.debug("Adding DUMMY2")
	componentName = "DUMMY2"
	ctx.myDict["Component"].append(componentName)
	ctx.myDict[componentName] = []
	ctx.myDict[componentName].append(ctx.current_lineNo -1) 
	newState = 'END'

	return (newState, lines[1:])

def end_fsm(ctx, lines):

	logging.info('END OF SUCCESSFUL FILE PARSING')
	logging.info('ReleaseNotes parsed data %s', ctx.myDict)

	processParsedData(ctx)
	ctx.release = ''
	ctx.platform = ''
	ctx.myDict = {}
	ctx.myDict["Component"] = []
	ctx.current_lineNo = -1
	newState = 'CLEANUP'
	return (newState, lines)

def cleanUp(ctx, lines):
	pass

def processParsedData(ctx):
	'''
	1. Take one by one the Components C1
	2. For each component, note its L = index+!
	3. Go to next compenent C2 in list and not its R = index - 1
	4. Grab the lines for C1 --> (L,R)
	5. Append these lines for C1 key into the key's array
	'''
	release = ctx.release
	platform = ctx.platform

	for component in ctx.myDict["Component"]:
		if component == "DUMMY1" or component == "DUMMY2":
			continue
		L = ctx.myDict[component][0] + 1
		R = ctx.myDict[ctx.myDict["Component"][ctx.myDict["Component"].index(component)+1]][0] - 1
		del ctx.myDict[component][0]
		logging.info('L=%s,R=%s',L,R)
		for n in range(L,R+1):
			logging.info('L=%s:,R=%s: n=%s:, line[n]=%s:',L,R,n,ctx.lines[n])
			l = re.sub('\s{2,}|\t*(\s)+\t+','#@#@',ctx.lines[n].strip('')).split('#@#@')
			if (len(l) != 3):
#					print(l,len(l))
				pass
			ctx.myDict[component].append(l)
		ctx.myDict[component].sort()
		
		if component in ctx.table_rows.keys():
			for elem in ctx.myDict[component]:
				if elem in ctx.table_rows[component]:
					continue
				else:
					ctx.table_rows[component].append(elem)
			ctx.table_rows[component].sort(key=lambda x: x[0])
		else:
			ctx.table_rows[component] = ctx.myDict[component] 
			ctx.table_rows[component].sort(key=lambda x: x[0])
		
	ctx.myDict["Component"].remove("DUMMY1")
	ctx.myDict["Component"].remove("DUMMY2")
	del ctx.myDict["DUMMY1"]
	del ctx.myDict["DUMMY2"]
	ctx.myDict["Component"].sort()
	ctx.finalData[release][platform] = copy.deepcopy(ctx.myDict)
	logging.info('ctx.myDictionary: %s', ctx.myDict)
	del ctx.myDict

class ParsedContext:
	def __init__(self):
		self.current_state = "START"
		self.release = ''
		self.platform = ''
		self.finalData = {}
		self.myDict = {}
		self.myDict["Component"] = []
		self.current_lineNo = -1
		self.lines = []
		self.table_rows = {}

def parseReleaseNotes(fileList):

	logging.basicConfig(filename='oneview.log', filemode='w', format='%(levelname)s - %(message)s', level=logging.INFO)
#	logging.basicConfig(format='%(levelname)s - %(message)s', level=logging.DEBUG)
	
	m = StateMachine()

	m.add_state("START", startFSM)
	m.add_state("FETCH_REL_PLAT", fetchReleaseAndPlatform)
	m.add_state("FETCH_COMPONENTS", fetchComponents)
	m.add_state("FETCH_COMPONENTS_DATA", fetchComponents)
	m.add_state("FETCH_HDD_COMPONENT", fetchHddComponent)
	m.add_state("FETCH_HDD_COMPONENT_DATA", fetchHddComponent)
	m.add_state("MISSING_REL_PLAT", None, end_state=1)	
	m.add_state("MISSING_COMPONENTS", None, end_state=1)	
	m.add_state("MISSING_HDD_COMPONENT", None, end_state=1)	
	m.add_state("MISSING_COMPONENT_END_MAKRER", None, end_state=1)	
	m.add_state("EOF_IN_FETCH_COMPONENTS", None, end_state=1)
	m.add_state("EOF_IN_FETCH_HDD_COMPONENT", addDummyMarkerAfterHdd)
	m.add_state("END", end_fsm)
	m.add_state("CLEANUP", None, end_state=1)

	ctx = ParsedContext()

	for i in fileList:
		with open(i, 'r') as f:
			ctx.current_state = 'START'
			m.set_start("START")
			logging.info('Now Parsing: %s', i)
			ctx.lines = f.readlines()
			ctx.lines =list(map(str.strip, ctx.lines))
			ctx.lines = list(filter(lambda a: a != '', ctx.lines))
			m.run(ctx, ctx.lines)
 
def generateComparisonReport(fileList):
	#open all the files
	finalData   = {}
	tableHeader = {}
	table_rows  = {}
	htmlReport  = []
	for i in fileList:
		'''
		1.Extract the release name
		2.Extract the server name
		'''
		myDict = {}
		myDict["Component"] = []
		with open(i, 'r') as f:
			lines = f.readlines()
			lines =list(map(str.strip, lines))
			lines = list(filter(lambda a: a != '', lines))
			lineNo = 0
			captureStart = False
			captureHDD   = False
			release = ""
			platform = ""
			skipLine = False
			for line in lines:
				if skipLine:
					skipLine = False
					continue

				z = re.search(r'ucs-(.*?)-huu-(.*?).iso', line)
				if z:
					platform = z.group(1)
					release  = z.group(2)
					if release != "":
						if release in finalData.keys():
							if platform != "":
								if platform in finalData[release].keys():
									print('dropping & exiting since '+ i +' already processed\n')
									sys.exit()
								finalData[release][platform] = {}
							else:
								print("Error fetching 'platform'")
								sys.exit()
						else:
							finalData[release] = {}
							if platform != "" :
						  		finalData[release][platform] = {}
							else:
								print("Error fetching 'platform'")
								sys.exit()
								
					else:
					   print("Error fetching 'release'")
					   sys.exit()

				z = re.search(r'^\s*(\b([A-Z-]+){1}\b)\s*$', line)
				if z:
					componentName = z.group(1)
					myDict["Component"].append(componentName)
					myDict[componentName] = []
					myDict[componentName].append(lineNo)
					captureStart = True

				if captureStart:
					z = re.search(r'(^[\s]*[-]+[\s]*$)|(^[\s]*$|^HDD)', line)
					if z:
						captureStart = False
						componentName = "DUMMY1"
						myDict["Component"].append(componentName)
						myDict[componentName] = []
						myDict[componentName].append(lineNo)
				
				z = re.search(r'^[\s\t]*(HDD)[\s*\t*]+Model[\s\t]+Latest[\s\t]+([Ff][Ww]|firmware)', line, re.MULTILINE|re.IGNORECASE)
				if z:
					componentName = z.group(1)
					myDict["Component"].append(componentName)
					myDict[componentName] = []
					myDict[componentName].append(lineNo + 1)
					captureHDD = True
					skipLine = True

				if captureHDD:
					z = re.search(r'(^[\s]*[-]+[\s]*$)|(^[\s]*$)', line)
					if z:
						captureHDD = False
						componentName = "DUMMY2"
						myDict["Component"].append(componentName)
						myDict[componentName] = []
						myDict[componentName].append(lineNo + 1)
				lineNo += 1
			#sort the "Component" list
			if captureHDD:
				captureHDD = False
				componentName = "DUMMY2"
				myDict["Component"].append(componentName)
				myDict[componentName] = []
				myDict[componentName].append(lineNo + 1)
		'''
		1. Take one by one the Components C1
		2. For each component, note its L = index+!
		3. Go to next compenent C2 in list and not its R = index - 1
		4. Grab the lines for C1 --> (L,R)
		5. Append these lines for C1 key into the key's array
		'''
		for component in myDict["Component"]:
			if component == "DUMMY1" or component == "DUMMY2":
				continue
			L = myDict[component][0] + 1
			R = myDict[myDict["Component"][myDict["Component"].index(component)+1]][0] - 1
			del myDict[component][0]
			for n in range(L,R+1):
				l = re.sub('\s{2,}|\t*(\s)+\t+','#@#@',lines[n].strip('')).split('#@#@')
				if (len(l) != 3):
#					print(l,len(l))
					pass
				myDict[component].append(l)
			myDict[component].sort()
			
			if component in table_rows.keys():
				for elem in myDict[component]:
					if elem in table_rows[component]:
						continue
					else:
						table_rows[component].append(elem)
				table_rows[component].sort(key=lambda x: x[0])
			else:
				table_rows[component] = myDict[component] 
				table_rows[component].sort(key=lambda x: x[0])
			
		myDict["Component"].remove("DUMMY1")
		myDict["Component"].remove("DUMMY2")
		del myDict["DUMMY1"]
		del myDict["DUMMY2"]
		myDict["Component"].sort()
		finalData[release][platform] = copy.deepcopy(myDict)
		print('myDictionary-->', myDict)
		del myDict
	print('myFinalDict-->', finalData)

	totalColumns = 3
	totalRelease = 0
	totalPlatforms = 0

	for release in reversed(sorted(finalData.keys())):
		totalRelease += 1
		for platform in sorted(finalData[release].keys()):
			totalPlatforms += 1

	totalColumns = totalPlatforms + totalColumns
	htmlRow = ['&#10006'] * totalColumns
	ii = -1

	newHTML = {}

	for component in sorted(table_rows.keys()):
		newHTML[component] = []
		componentHTMLReport = []
		ii = -1
		for release in reversed(sorted(finalData.keys())):
			print('RELEASE', release)
			for platform in sorted(finalData[release].keys()):
				ii += 1
				print('PLATFORM', platform)
				if component in finalData[release][platform].keys():
					for row in table_rows[component]:
						
						htmlRow = ['&#10006'] * totalColumns
						
						newL = len(row)
						markExp = False
						if newL > 3:
							row[(3-1):newL] = [''.join(row[(3-1):newL])]
							markExp = True
				
						i = 0
						for elem in row:
							htmlRow[i] = elem
							i += 1	
							
						if row in finalData[release][platform][component]:
							print('CHECKING ROW', row)
							'''
							check if 'row' is present in htmlReport
							if present then mark it Y
							if not present then add it and mark it Y
							'''
							indexInHtmlReport = 0
							rowInHtmlPresent =  False
							for rowHtml in componentHTMLReport:
								tempList = [ rowHtml[0], rowHtml[1], rowHtml[2] ]
								if tempList == row:
									rowInHtmlPresent = True
									break
								indexInHtmlReport += 1
							
							if rowInHtmlPresent:
								print('ROW PRESENT', ii, componentHTMLReport[indexInHtmlReport])
								componentHTMLReport[indexInHtmlReport][ii + 3] = '&#10003'
							else:
								print('ROW ABSENT')
								print('ROW INSERTED BEFORE', ii, htmlRow)
								htmlRow[ii + 3] = '&#10003'
								print('ROW INSERTED AFTER', ii, htmlRow )
								componentHTMLReport.append(htmlRow)

		newHTML[component] = componentHTMLReport

#generating a table with all rows; starting with headers
#no key,value

	dataToRender = []

	#adding headers
	tableHeaders = [['X','X','X'], ['Component','Description','Firmware Version']]
	index = len(tableHeaders[0])	
	for i in range(len(tableHeaders)):

		index = len(tableHeaders[i])	
		htmlRow = ['&#10006'] * totalColumns
		htmlRow = tableHeaders[i]
		for release in reversed(sorted(finalData.keys())):
			for platform in sorted(finalData[release].keys()):
				if i == 0:
					htmlRow.insert(index, release)
				else:
					htmlRow.insert(index, platform)
				index += 1
		
		dataToRender.append(htmlRow)

	#adding all rows for each component
	for component in sorted(newHTML.keys()):
		htmlRow = ['&#10006'] * totalColumns
		htmlRow[0] = component
		dataToRender.append(htmlRow)
		for row in newHTML[component]:
			dataToRender.append(row)
		

#generating a table with all rows
#	print(newHTML)
	print(dataToRender)
	
	with open("report.html",'w') as w:
		with open("template.html", 'r') as T:
			temp = T.read()
			t = Template(temp)
			w.write(t.render(rData=dataToRender, header=finalData))

def main():
	#generateComparisonReport(sys.argv[1:])
	parseReleaseNotes(sys.argv[1:])

if __name__ == '__main__':
  main()
