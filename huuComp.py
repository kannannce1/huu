#!/usr/bin/env python3
import sys
import re
import copy
import logging
import shlex
import json

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
			if newState.upper() in self.endStates:
				logging.info("Moving into end state %s", newState)
				break
			else:
				ctx.current_lineNo += 1
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
						logging.critical('duplicate REL=%s PLAT=%s, skipping', release, platform)
						newState = 'DUPLICATE_REL_PLAT'
						return (newState, lines[1:])
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
		newState = "MISSING_COMPONENTS"
		return (newState, lines)

	componentName = ""
	newState = ctx.current_state

	if ctx.isNewRelNoteFormat:
		z = re.search(r"^\s*\'(([A-Z-]+){1})\'\s*$", line)
	else:
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
		if ctx.current_state == 'FETCH_HDD_COMPONENT':
			newState = 'MISSING_HDD_COMPONENT'
		else:
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
	ctx.myDict[componentName].append(ctx.current_lineNo)
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
	ctx.isNewRelNoteFormat = True
	newState = 'CLEANUP'
	return (newState, lines)

def end_fsm_error(ctx, lines):

	logging.info('FILE PARSING FAILED: skipping this file')

	ctx.release = ''
	ctx.platform = ''
	ctx.myDict = {}
	ctx.myDict["Component"] = []
	ctx.current_lineNo = -1
	ctx.isNewRelNoteFormat = True
	newState = 'CLEANUP'
	return (newState, lines)

def cleanUp(ctx, lines):
	pass

def splitOnErr(str1,c):

	str1 = str1.strip()
	str2 = " "
	l = ['','','']
	l[2] = str1[str1.rfind(str2)+1:]
	index = str1.rfind(str2)

	while str1[index] == ' ':
		index = index -1

	if c == 'HDD':

		l[1] = str1[str1.rfind(str2, 0, index)+1: index+1]

		index = str1.rfind(str2, 0, index)

		while str1[index] == ' ':
			index = index -1

		l[0] = str1[:index+1]

	else:

		l[0] = str1[:str1.find(str2)]
		indexL = str1.find(str2)

		t = str1[indexL:index+1]
		t = t.strip()
		l[1] = t

	l = [e.strip("'") for e in l]
	return l

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
		for n in range(L,R+1):
			l = []
			logging.debug('L=%s:,R=%s: n=%s:, line[n]=%s:',L,R,n,ctx.lines[n])
			if ctx.isNewRelNoteFormat:
				try:
					l = shlex.split(ctx.lines[n])
					if (len(l) != 3):
						assert (False),'unexpected; NewRelNoteFormat !=3 columns'
				except ValueError:
					logging.debug("ValueError: No closing quotation cols=%s line=%s", len(l), l)
					l = splitOnErr(ctx.lines[n],component)
					logging.debug("shlex parsing error, after splitOnErr cols=%s line=%s ",len(l),l)
					if ((l[0] == l[2]) and (l[1] == '')):
						logging.critical('FILE contain INVALID lines')
						continue
			else:
				l = re.sub('\s{2,}|\t*(\s)+\t+','#@#@',ctx.lines[n].strip('')).split('#@#@')
				if (len(l) != 3):
					logging.debug("parsing error, found in component=%s cols=%s line=%s, using splitOnErr ",component,len(l),l)
					l = splitOnErr(ctx.lines[n],component)
					logging.debug("parsing error, after splitOnErr in component=%s cols=%s line=%s ",component,len(l),l)
			'''
			swap column 0 & 1 if the component is HDD
			to maintain the uniformity of table format
			'''
			if component == "HDD":
				temp = l[1]
				l[1] = l[0]
				l[0] = temp

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

def generateHtmlCompatibleData(ctx):

	totalColumns = 4
	totalRelease = 0
	totalPlatforms = 0

	release = ctx.release
	platform = ctx.platform

	for release in reversed(sorted(ctx.finalData.keys())):
		totalRelease += 1
		for platform in sorted(ctx.finalData[release].keys()):
			totalPlatforms += 1

	totalColumns = totalPlatforms + totalColumns
	htmlRow = ['N'] * totalColumns
	ii = 0

	for component in sorted(ctx.table_rows.keys()):
		ctx.newHTML[component] = []
		componentHTMLReport = []
		ii = -1
		for release in reversed(sorted(ctx.finalData.keys())):
			for platform in sorted(ctx.finalData[release].keys()):
				ii += 1
				if component in ctx.finalData[release][platform].keys():
					for row in ctx.table_rows[component]:

						if row in ctx.finalData[release][platform][component]:
							htmlRow = ['N'] * totalColumns

							newL = len(row)
							if newL > 3:
								row[(3-1):newL] = [''.join(row[(3-1):newL])]
								htmlRow[0] = '$$@@'
							elif newL == 2:
								htmlRow[0] = '$$@@'
								row.append('parseError')
							elif newL == 1:
								htmlRow[0] = '$$@@'
								row.append('parseError')
								row.append('parseError')
							else:
								pass

							i = 1

							for elem in row:
								htmlRow[i] = elem
								i += 1
								print('CHECKING ROW', row)
							'''
							check if 'row' is present in htmlReport
							if present then mark it Y
							if not present then add it and mark it Y
							'''
							indexInHtmlReport = 0
							rowInHtmlPresent =  False
							for rowHtml in componentHTMLReport:
								irow = [row[0],row[2]]
								irowHtml = [rowHtml[1],rowHtml[3]]
								if irow == irowHtml:
									rowInHtmlPresent = True
									break
								indexInHtmlReport += 1

							if rowInHtmlPresent:
								yy = componentHTMLReport[indexInHtmlReport][ii + 4]

								if yy != row[2] and yy != 'N':
									logging.debug('row present %s ',componentHTMLReport[indexInHtmlReport][ii + 4])
									assert False, 'same key:value pair expected, exiting'
								else:
									logging.debug('row present %s %s ',yy, componentHTMLReport[indexInHtmlReport][ii + 4])
									componentHTMLReport[indexInHtmlReport][ii + 4] = row[2]
							else:
								logging.debug('row absent adding now %s ', row)
								htmlRow[ii + 4] = row[2]
								componentHTMLReport.append(htmlRow)

		ctx.newHTML[component] = componentHTMLReport

def generateHTML(ctx):
	with open("report.html",'w') as w:
		with open("template.html", 'r') as T:
			logging.debug('Final HTML: %s', ctx.newHTML)

			with open("html.json", 'w') as J:
				jsonData = json.dumps(ctx.newHTML)
				J.write(jsonData)
			temp = T.read()
			t = Template(temp)
			w.write(t.render(rData=ctx.newHTML, header=ctx.finalData))

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
		self.newHTML = {}
		self.isNewRelNoteFormat = True

def parseReleaseNotes(fileList):

	logging.basicConfig(filename='oneview.log', filemode='w', format='%(levelname)s - %(message)s', level=logging.DEBUG)

	m = StateMachine()

	m.add_state("START", startFSM)
	m.add_state("FETCH_REL_PLAT", fetchReleaseAndPlatform)
	m.add_state("FETCH_COMPONENTS", fetchComponents)
	m.add_state("FETCH_COMPONENTS_DATA", fetchComponents)
	m.add_state("FETCH_HDD_COMPONENT", fetchHddComponent)
	m.add_state("FETCH_HDD_COMPONENT_DATA", fetchHddComponent)
	m.add_state("MISSING_REL_PLAT", end_fsm_error)
	m.add_state("DUPLICATE_REL_PLAT", end_fsm_error)
	m.add_state("MISSING_COMPONENTS", end_fsm_error)
	m.add_state("MISSING_HDD_COMPONENT", end_fsm)
	m.add_state("EOF_IN_FETCH_HDD_COMPONENT", addDummyMarkerAfterHdd)
	m.add_state("END", end_fsm)
	m.add_state("CLEANUP", None, end_state=1)

	ctx = ParsedContext()

	for i in fileList:
		with open(i, 'r') as f:
			z = re.search(r'^\s*(CISCO)\s*$', f.read(), re.MULTILINE)
			if z:
				logging.debug("using old relNotes format parser")
				ctx.isNewRelNoteFormat = False

			f.seek(0,0)

			z = re.search(r"^\s*'(CISCO)'\s*$", f.read(), re.MULTILINE)
			if z:
				logging.debug("using new relNotes format parser")
				ctx.isNewRelNoteFormat = True

			f.seek(0,0)

			ctx.current_state = 'START'
			m.set_start("START")
			logging.info('Now Parsing: %s, from file=%s', i, ctx.current_lineNo)
			ctx.lines = f.readlines()

			ctx.lines =list(map(str.strip, ctx.lines))
			ctx.lines = list(filter(lambda a: a != '', ctx.lines))
			m.run(ctx, ctx.lines)

	logging.info('MERGED data: %s', ctx.finalData)
	generateHtmlCompatibleData(ctx)
	generateHTML(ctx)

def main():
	#generateComparisonReport(sys.argv[1:])
	parseReleaseNotes(sys.argv[1:])

if __name__ == '__main__':
	main()
