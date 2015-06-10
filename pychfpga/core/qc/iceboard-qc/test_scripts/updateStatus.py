import statusReport
from statusReport import EMPTY_TEST_STATUS
import addNote

#This script manually gets the test status from a user and updates the relevant files.
def updateManually( ):
    board = statusReport.getBoardInfo()
#    confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
#    if confirm == 'y' or confirm == 'Y':
#        statusReport.appendLatex( statusReport.formatLatex(board) )
    fname = 'board' + str(board[1]) + '.txt'
    confirm = raw_input("\nWould you like to add these results to the " + fname + " file status report? (y/n)\t")
    if confirm == 'y' or confirm == 'Y':
        statusReport.appendTXT( fname, statusReport.formatTXT( board) )
        
def update ( board = EMPTY_TEST_STATUS() ):
    confirm = raw_input( "Would you like to update the status report for this board? (this will overwrite previous status report) (y/n)\t" )
    if confirm != 'Y' and confirm != 'y':
        pass
    else:
#        confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
#        if confirm == 'y' or confirm == 'Y':
#            statusReport.appendLatex( statusReport.formatLatex(board) )
        fname = 'board' + str(board[1]) + '.txt'
        statusReport.appendTXT( fname, statusReport.formatTXT( board ) )
            
    confirm = raw_input( "\nWould you like to add anything to the 'Board Notes' at the top of the file? (y/n)\t" )
    if confirm != 'Y' and confirm != 'y':
        return
    else:
        addNote.addNote( 'board' + board[1] + '.txt' )
