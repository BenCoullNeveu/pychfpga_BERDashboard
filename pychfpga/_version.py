__version__ = "2.0"

# Git version
def get_git_version():

    import os
    import subprocess

    PROGRAM = os.path.realpath(__file__)
    try:
        return subprocess.check_output(
            'git describe --all --dirty --long'.split(),
            cwd = os.path.dirname(PROGRAM)).decode().strip()
    except Exception:
        print('GIT was not found')
        return 'unknown' # JFC: To allow tests in windows
