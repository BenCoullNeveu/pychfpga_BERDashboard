'''
Collection of functions used by many of the scripts for variety of things,
but that don't fit into any of the other modules.
'''

def read_config():
    '''
    Simply reads the 'config.yaml' file, or 'config_example.yaml' if there is no user configure one.
    If the example is read, the 'default_config' key is set to True.
    :return: Dictionary of config parameters. An extra key 'default_config' is True if no 'config.yaml' file was found,
     indicating that 'config_example.yaml' was used instead.
    '''
    import yaml
    import os

    if os.path.isfile('config.yaml'):
        config = yaml.load(open('config.yaml'))
        config['default_config'] = False
    else:
        config = yaml.load(open('config_example.yaml'))
        config['default_config'] = True
    return config

def get_repo(repo_name='iceboard_qc'):
    ''' Just returns an instance of the specified git repository
    :return: Repo object for the specified repository (iceboard_qc or ch_acq or chFPGA, though not all implemented yet)
    '''
    import git
    return git.Repo('../') #TODO: change this when moving to ch_acq

#Common date formatting for testing functions
def date_format(date, short = False):
    '''
    formats date: converts to string and adds 0 if <10 for day, month
    (legacy function)
    '''
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