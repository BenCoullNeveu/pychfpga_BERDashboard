import statusReport

#This script manually gets the test status from a user and updates the relevent files.
def updateManually( ):
    board = statusReport.getBoardInfo()
    confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
    if confirm == 'y' or confirm == 'Y':
        statusReport.appendLatex( statusReport.formatLatex(board) )
    fname = 'board' + str(board[1]) + '.txt'
    confirm = raw_input("\nWould you like to add these results to the " + fname + " file status report? (y/n)\t")
    if confirm == 'y' or confirm == 'Y':
        statusReport.appendTXT( fname, statusReport.formatTXT( board) )
        
def update ( board = [ '', '', '', None, None, None, None, None, None, None, None, '', '' ] ):
    confirm = raw_input( "Would you like to update the status report for this board? (this will overwrite previous status report) (y/n)\t" )
    if confirm != 'Y' and confirm != 'y':
        return
    else:
        confirm = raw_input("\nWould you like to append these results to the inventory.tex file? (y/n)\t")
        if confirm == 'y' or confirm == 'Y':
            statusReport.appendLatex( statusReport.formatLatex(board) )
        fname = 'board' + str(board[1]) + '.txt'
        confirm = raw_input("\nWould you like to add these results to the " + fname + " file status report? (y/n)\t")
        if confirm == 'y' or confirm == 'Y':
            statusReport.appendTXT( fname, statusReport.formatTXT( board ) )
