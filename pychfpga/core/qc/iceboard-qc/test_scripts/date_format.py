#Common date formatting for testing functions
def date_format(date, short = False):
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
    
    if short: # return 'dd/mm/yy'
        return day + '/' + month + '/' + year[2:4]
    else: # return 'dd/mm/yyyy, hh:mm'
        return day + '/' + month + '/' + year + ', ' + hour + ':' + minute