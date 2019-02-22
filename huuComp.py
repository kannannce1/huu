#!/usr/bin/python
import sys
import re
import copy
import logging
import json

from jinja2 import Template

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
					print('Found',componentName)
					myDict["Component"].append(componentName)
					myDict[componentName] = []
					myDict[componentName].append(lineNo)
					captureStart = True

				if captureStart:
					print('CAP START', line, lineNo)
					z = re.search(r'(^[\s]*[-]+[\s]*$)|(^[\s]*$|^HDD)', line)
					if z:
						print('CAP MATCH', z.group(1), z.group(2))
						captureStart = False
						componentName = "DUMMY1"
						myDict["Component"].append(componentName)
						myDict[componentName] = []
						myDict[componentName].append(lineNo)
				
				z = re.search(r'^[\s\t]*(HDD)[\s*\t*]+Model[\s\t]+Latest[\s\t]+([Ff][Ww]|firmware)', line, re.MULTILINE|re.IGNORECASE)
				if z:
					print('CAP HDD')
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
					print('EXCEPTION DETECTED',l,len(l))
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

	totalColumns = 4
	totalRelease = 0
	totalPlatforms = 0

	for release in reversed(sorted(finalData.keys())):
		totalRelease += 1
		for platform in sorted(finalData[release].keys()):
			totalPlatforms += 1

	totalColumns = totalPlatforms + totalColumns
	htmlRow = ['N'] * totalColumns
	ii = 0

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
							
						if row in finalData[release][platform][component]:
							htmlRow = ['N'] * totalColumns
							
							newL = len(row)
							if newL > 3:
								row[(3-1):newL] = [''.join(row[(3-1):newL])]
								htmlRow[0] = '$$@@'
							elif newL < 3:
								htmlRow[0] = '$$@@'
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
								tempList = rowHtml[1:4]
								if tempList == row:
									rowInHtmlPresent = True
									break
								indexInHtmlReport += 1
							
							if rowInHtmlPresent:
								print('ROW PRESENT', ii, componentHTMLReport[indexInHtmlReport])
								componentHTMLReport[indexInHtmlReport][ii + 4] = 'Y'
							else:
								print('ROW ABSENT')
								print('ROW INSERTED BEFORE', ii, htmlRow)
								htmlRow[ii + 4] = 'Y'
								print('ROW INSERTED AFTER', ii, htmlRow )
								componentHTMLReport.append(htmlRow)

		newHTML[component] = componentHTMLReport

#adding headers as part of table
		componentHTMLReport = []
		'''
		tableHeaders = [['X', 'X','X','X'], ['X', 'Component','Description','Firmware Version']]
		index = len(tableHeaders[0])	
		for i in range(len(tableHeaders)):

			index = len(tableHeaders[i])	
			htmlRow = ['N'] * totalColumns
			htmlRow = tableHeaders[i]
			for release in reversed(sorted(finalData.keys())):
				for platform in sorted(finalData[release].keys()):
					if i == 0:
						htmlRow.insert(index, release)
					else:
						htmlRow.insert(index, platform)
					index += 1
			
			componentHTMLReport.append(htmlRow)

		newHTML["Headers"] = componentHTMLReport
		'''
#adding header as part of table

#generating a table with all rows; starting with headers
#no key,value
	'''
	dataToRender = []

	#adding headers
	tableHeaders = [['', 'X','X','X'], ['', 'Component','Description','Firmware Version']]
	index = len(tableHeaders[0])	
	for i in range(len(tableHeaders)):

		index = len(tableHeaders[i])	
		htmlRow = ['N'] * totalColumns
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
		htmlRow = ['N'] * totalColumns
		htmlRow[0] = component
		dataToRender.append(htmlRow)
		for row in newHTML[component]:
			dataToRender.append(row)
		
	print(dataToRender)
	'''

#generating a table with all rows
#	print(newHTML)
	with open('dataToRender.json', 'w') as J:
		J.write(json.dumps(newHTML))

	print(newHTML)
	
	with open("report.html",'w') as w:
		with open("template.html", 'r') as T:
			temp = T.read()
			t = Template(temp)
			afterTemplating = t.render(rData=newHTML, header=finalData)
			print(afterTemplating)
			w.write(afterTemplating)

def main():
	generateComparisonReport(sys.argv[1:])

if __name__ == '__main__':
  main()
