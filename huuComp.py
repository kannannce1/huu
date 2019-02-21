#!/usr/bin/python
import sys
import re
import copy
import logging

from jinja2 import Template

s1 = """
<!DOCTYPE html>
<html>
<head>
<style type="text/css">

table {
	border-collapse: collapse;
	background-color: #f3f3f3;
}
td {
	border: 1px solid black;
	text-align: left;
	padding: 15px;
}

th {
	border: 1px solid black;
	text-align: left;
	padding: 15px;
	bgcolor="#004BAF";
	color=white;
}

#marker {
	text-align:center;
	color:blue;
}

</style>
<script src="https://code.jquery.com/jquery-1.12.4.min.js" 
        integrity="sha384-nvAa0+6Qg9clwYCGGPpDQLVpLNn0fRaROjHqs13t4Ggj3Ez50XnGQqc/r8MhnRDZ" 
		crossorigin="anonymous">
</script>


</head>

<body>
<h1>UCS C-Series Rack-Mount Standalone Server Software Comparison</h1>

{% set ns = namespace() %}
{% set ns.total_cols = 0 %}
{% set ns.i = 0 %}

<table>
<thead>

{% for component in rData|dictsort %}
	{% if component[1] == "Headers" %}
		{% for rowElem in component[1] %}
		{% set ns.total_cols = 0 %}
<tr>
			{% for cell in rowElem %}
	  		 	<th > {{ cell }} </th>
				{% set ns.total_cols = ns.total_cols + 1  %}
			{% endfor  %}
</tr>
		{% endfor %}
	{% endif %}
{% endfor %}
</thead>
<tbody>


{% for component in rData|dictsort %}
	{% if component[1] != "Headers" %}
<tr>
	<th style="font-size:160%;" bgcolor="#009edc" colspan="{{ ns.total_cols }}"> {{ component[0] }} </th>
</tr>
		{% for rowElem in component[1] %}
	<tr>
				{% set ns.i = 0 %}
			{% for cell in rowElem %}
				{% if ns.i < 3 %}
				 <td > {{ cell }} </td>
				{% else  %}
				 <td id="marker"> {{ cell }} </td>
				{% endif %}
				{% set ns.i = ns.i +1  %}
			{% endfor  %}
	</tr>
		{% endfor %}
	{% endif %}
{% endfor %}

</tbody>
</table>
<script src="./jquery-freeze-table-master/dist/js/freeze-table.js"></script>
<script>
$(".example").freezeTable({
		'columnNum': 3
		});
</script>
</body>
</html>
"""
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

#adding headers as part of table
		componentHTMLReport = []

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
			
			componentHTMLReport.append(htmlRow)

		newHTML["Headers"] = componentHTMLReport

#adding header as part of table
	print(newHTML)
	
	with open("report.html",'w') as w:
		t = Template(s1)
		w.write(t.render(rData=newHTML, header=finalData))

def main():
	generateComparisonReport(sys.argv[1:])

if __name__ == '__main__':
  main()
