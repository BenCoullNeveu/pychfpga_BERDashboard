from statusReport import STATUS_LINES
from other_stuff import date_format
import time
import os

def addNote( fname ):
    appendNote( fname, getNotes() )

def getNotes( ):
    input = raw_input("Please enter any modified components or other relevant notes here (these will be added to the 'Board Notes' section at top of file):\n")
    return [ '| ' + date_format(time.localtime()) + ':    ' + input + '\n\n']

def appendNote( fname, newLines = [] ):
    #check file exists
    if not os.path.isfile(fname):
        print "\nFile " + fname + " doesn't exist."
        return
    #read file as list
    f = open(fname, 'r')
    content = f.readlines()
    f.close()

    #look for marker line in file
    linePos = 9 #default position to append, otherwise will append where previous Notes were, or following status report
    foundNotes = False
    for index, line in enumerate(content): #find previously existing section
        if line == "Board Notes\n":
            foundNotes = True
            linePos = index
            foundEnd = False
            for index2, line2 in enumerate(content,index): #find end marker
                if line2 == '(add here)\n':
                    linePos = index2 - index
                    foundEnd = True
                    break
            if not foundEnd:
                print("Missing marker '(add here)' at the end of previous notes. Quitting.")
                return
            print("Found previous Notes. Will append to these.")
            break
    if not foundNotes:
        newLines.insert(0,"------\n")
        newLines.insert(0,"Board Notes\n")
        newLines.append("|(add here)\n")
        newLines.append("\n")
        print("Did not find previous Notes. Creating new section.")
        for index, line in enumerate(content):
            if line == "Status report of most recent test (Please don't modify this line or add any lines in this block)\n":
                linePos = index + STATUS_LINES()
                break

    #insert lines and write to file
    content[linePos:linePos] = newLines
    f = open(fname, 'w')
    f.writelines(content)
    f.close()
    print "Successfully added note."
