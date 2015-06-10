'''This is a collection of functions that edit the RestructuredText board results files.
Functions that were previously found in their own 'addNote.py' and 'updateStatus.py' have been moved here.
'''

from other_stuff import date_format
from statusReport import STATUS_LINES
import time
import os
import statusReport
from statusReport import EMPTY_TEST_STATUS
from other_stuff import read_config

def new_file_header(fname, board_sn, board_md, board_vn, pcb_sn):
    if not os.path.isfile(fname):
        file = open(fname, 'w')
        file.write('=========================\n')
        file.write('ICE board ' + board_sn + 'QC testing\n')
        file.write('=========================\n')
        file.write('| Quality control testing results for ICE board serial number ' + board_sn + '\n')
        file.write('| Revision number: ' + board_vn + '\n')
        file.write('| Board model: ' + board_md + '\n')
        file.write('| PCB serial: ' + pcb_sn + '\n')
        date_str=date_format(time.localtime())
        file.write('| File created on : ' + date_str + '\n')
        file.write('\n\n---------------------\n\n')
        file.close()
        print "File " + fname + " was created.\n"
    else:
        print "File already exists! Leaving as is.\n"

def addNote( fname ):
    '''
    Prompts the user for input and adds it to the specified file's Board Notes section.
    :param fname: Name of board file to append to (e.g. 'board0012.txt')
    '''
    input = raw_input("Please enter any modified components or other relevant notes here (these will be added to the 'Board Notes' section at top of file):\n")
    appendNote( fname, ['| ' + date_format(time.localtime()) + ':    ' + input + '\n'] )

def appendNote( fname, newLines = [] ):
    '''
    Finds the 'Board Notes' section in the specified file and appends given lines to it.
    Users should use 'addNote()', since it uses the standard format.
    :param fname: Name of board file to append to (e.g. 'board0012.txt')
    :param newLines: List of lines to append. Should be formatted appropriately (i.e. see 'addNote()')
    '''
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
                if line2 == '| (add here)\n':
                    linePos = index2 - index
                    foundEnd = True
                    break
            if not foundEnd:
                print("Missing marker '(add here)' at the end of previous notes. Quitting.")
                return
            print("Found previous Notes. Will append to these.")
            break
    if not foundNotes:
        newLines.insert(0,"-----------\n")
        newLines.insert(0,"Board Notes\n")
        newLines.append("| (add here)\n")
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

def updateStatusManually( ):
    '''
    Prompts user for test results for a board and updates that board file.
    To leave a previous result entry unchanged, enter 'None' for when prompted for that test
    '''
    board = statusReport.getBoardInfo()
#    confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
#    if confirm == 'y' or confirm == 'Y':
#        statusReport.appendLatex( statusReport.formatLatex(board) )
    fname = os.path.join(read_config()['results_directory'],'board' + str(board[1]) + '.txt')
    confirm = raw_input("\nWould you like to add these results to the " + fname + " file status report? (y/n)\t")
    if confirm == 'y' or confirm == 'Y':
        statusReport.appendTXT( fname, statusReport.formatTXT( board) )

def updateStatus( board = EMPTY_TEST_STATUS() ):
    '''
    Updates test status to the supplied list of results.
    :param board: List of test results for that board. Uses format from 'statusReport.EMPTY_TEST_STATUS()'.
    '''
    fname = os.path.join(read_config()['results_directory'],'board' + str(board[1]) + '.txt')
    confirm = raw_input( "Would you like to update the status report for this board? (this will overwrite previous status report) (y/n)\t" )
    if confirm != 'Y' and confirm != 'y':
        pass
    else:
#        confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
#        if confirm == 'y' or confirm == 'Y':
#            statusReport.appendLatex( statusReport.formatLatex(board) )
        statusReport.appendTXT( fname, statusReport.formatTXT( board ) )

    confirm = raw_input( "\nWould you like to add anything to the 'Board Notes' at the top of the file? (y/n)\t" )
    if confirm != 'Y' and confirm != 'y':
        return
    else:
        addNote( fname )
