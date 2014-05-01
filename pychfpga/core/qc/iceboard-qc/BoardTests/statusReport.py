import os
import time

#Takes input from user, returns array of True/False (and string for comments) for test status: [ tester's name, serial, revision, inspection, resistance, DC, PLL, ARM, FPGA, FGPA test, GTX, comments ]
def getBoardInfo():
    tester = raw_input("Please enter your name\t")
    board = raw_input("Please enter board serial number (e.g. 0025)\t")
    revision = raw_input("Please enter board revision (e.g. Rev2)\t")
    print("\nPlease indicate whether the board passed the following tests.")
    print("Enter 'y' or '' for a PASS, 'n' for a FAIL, or 'None' if the test wasn't performed.\n")
    inspection = checkInput( raw_input("Inspection test:\n") )
    resistance = checkInput( raw_input("Resistance test:\n") )
    dc = checkInput( raw_input("DC test:\n") )
    pll = checkInput( raw_input("Program PLL:\n") )
    arm = checkInput( raw_input("Program ARM:\n") )
    fpga = checkInput( raw_input("Program FPGA:\n") )
    fpgaTest = checkInput( raw_input("FPGA test:\n") )
    gtx = checkInput( raw_input("Program GTX:\n") )
    comments = raw_input("Add any additional comments here:\t")
    
    return [ tester, board, revision, inspection, resistance, dc, pll, arm, fpga, fpgaTest, gtx, comments ]
    
def checkInput( input ):
    if input == 'y' or input == 'Y' or input == '':
        return True
    elif input == 'n' or input == 'N':
        return False
    elif input == 'None' or input == 'none':
        return None
    else:
        print "Can't parse input."
        return 'input error'

#Format for LaTex inventory.tex document. Takes list of form [ tester's name, serial, revision, inspection, resistance, DC, PLL, ARM, FPGA, FPGA Test, GTX, comments ]. Returns full line as string.
def formatLatex( inputList ):
    newLine = '\hline ' + date_format(time.localtime()) + ' & ' + inputList[0] + ' & ' + inputList[1] + ' & ' + inputList[2]
    for i in range(3,11):
        if inputList[i] ==  True:
            newLine += " & \\textcolor{green}{PASS}"
        elif inputList[i] == False:
            newLine += " & \\textcolor{red}{FAIL}"
        elif inputList[i] == None:
            newLine += " & N/A"
    newLine += ' & ' + inputList[11] + ' \\\\ \n'
    
    return newLine
    
#Format for %fname.tex document. Takes list of form [ tester's name, serial, revision, inspection, resistance, DC, PLL, ARM, FPGA, FPGA test, GTX, comments ]. Returns block of lines as list.
def formatTXT( inputList ):
    newLines = []
    newLines.append("|Status report of most recent test (Please don't modify this line or add any lines in this block)\n")
    newLines.append("|------\n")
    newLines.append('|Date: ' + date_format(time.localtime()) + '\n')
    newLines.append("|Tester: " + inputList[0] + "\n")
    newLines.append("|\n")
    
    #Convert True/False/None to PASS/FAIL/N/A
    testResult = []
    for i in range(3, 11):
        if inputList[i] ==  True:
            testResult.append("PASS")
        elif inputList[i] == False:
            testResult.append("FAIL")
        elif inputList[i] == None:
            testResult.append("N/A")
    newLines.append("|Inspection test: " + testResult[0] + "\n")
    newLines.append("|Resistance test: " + testResult[1] + "\n")            
    newLines.append("|DC test: " + testResult[2] + "\n")
    newLines.append("|Program PLL: " + testResult[3] + "\n")
    newLines.append("|Program ARM: " + testResult[4] + "\n")
    newLines.append("|Program FPGA: " + testResult[5] + "\n")
    newLines.append("|FPGA test: " + testResult[6] + "\n")
    newLines.append("|Program GTX: " + testResult[7] + "\n")
    newLines.append("|Comments: " + inputList[11] + "\n")
    newLines.append("|\n")
    newLines.append("|\n")
    
    return newLines
        
def appendLatex( newLine = '' ):
    #read file as list
    f = open('inventory/inventory.tex', 'r')
    content = f.readlines()
    f.close()
    
    #look for marker line in file
    foundLine = False
    for index, line in enumerate(content):
        if line == '%append new board here\n':
            foundLine = True
            linePos = index
    if foundLine == False:
        print "Couldn't find that line."
    
    #append new line describing board to that position
    content.insert(linePos, newLine)
    f = open('inventory/inventory.tex', 'w')
    f.writelines(content)
    f.close()
    
def appendTXT( fname, newLines = [] ):
    STATUS_LINES_NUM = 16 #number of lines in block of text to append (and possibly overwrite)
    
    #check file exists
    if not os.path.isfile(fname):
        print "\nFile " + fname + " doesn't exist."
        return
    #read file as list
    f = open(fname, 'r')
    content = f.readlines()
    f.close()
    
    #look for marker line in file
    linePos = 9 #default position to append, otherwise will append where previous report was
    foundLine = False
    for index, line in enumerate(content):
        if line == "|Status report of most recent test (Please don't modify this line or add any lines in this block)\n":
            foundLine = True
            linePos = index
            break
    #check that previous status report exists and is in expected format. If it is as expected, delete previous status report with user confirmation.
    if foundLine:
        overwrite = True
        for i in range(linePos, linePos + STATUS_LINES_NUM):
            if content[i][0] != '|':
                overwrite = False
                print "\nThere is something wrong with the previous status report that was found (should be " + str(STATUS_LINES_NUM) + " lines, with last 2 empty, and every line beginning with a '|')."
                print "To not take any chances, this script will not overwrite."
                print "\nWould you like to append this status report to the previous one or quit?"
                confirm = raw_input("Enter 'Y' or 'y' to continue, or anything else to quit.\t")
                if confirm != 'Y' and confirm != 'y':
                    print "\nStatus report not updated. You can do it manually by editing the file and running the updateStatus.updateManually()."
                    return
        if overwrite:
            confirm = raw_input("\nThis will overwrite previous status report.\nEnter 'Y' or 'y' to continue, or anything else to quit.\t")
            if confirm != 'Y' and confirm != 'y':
                print "\nStatus report not updated. You can do it manually by editing the file and running the updateStatus.updateManually()."
                return
            else: del content[linePos:(linePos + STATUS_LINES_NUM)]
    else:
        print "\nDid not find previous status report. Writing to default position."
    #insert lines and write to file
    content[linePos:linePos] = newLines
    f = open(fname, 'w')
    f.writelines(content)
    f.close()
    print "Status report successfully written."
    
def date_format(date):
    #finds the date, converts to string and adds 0 if <10 for day, month
    #day
    day=str(date[2])
    if int(day)<10:
        day ='0' + day
    #month
    month=str(date[1])
    if int(month)<10:
        month ='0' + month
    #year
    year=str(date[0])
    #hour
    hour=str(date[3])
    if int(hour)<10:
       hour ='0' + hour
    #minutes
    minute=str(date[4])
    if int(minute)<10:
        minute ='0' + minute
    
    #returns 'dd/mm/yyyy, hh:mm'
    return day + '/' + month + '/' + year + ', ' + hour + ':' + minute
    