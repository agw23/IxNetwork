"""
loadQuickTest.py:

   Tested with two back-2-back Ixia ports

   - Connect to the API server
   - Configure license server IP
   - Loads a saved Quick Test .ixncfg config file that is in the same local directory: QuickTestNgpf_vm8.20.ixncfg
   - Configure license server IP
   - Optional: Assign ports or use the ports that are in the saved config file.
   - Start all protocols
   - Verify all protocols
   - Start traffic 
   - Monitor Quick Test 
   - Copy Quick Test CSV result files
   - Copy PDF test result. This only for Windows. 
 

Supports IxNetwork API servers:
   - Windows, Windows Connection Mgr and Linux

Requirements
   - IxNetwork 8.50
   - Python 2.7 and 3+
   - pip install requests
   - ixnetwork_restpy v1.0.29
   - pip install -U --no-cache-dir ixnetwork_restpy

RestPy Doc:
    https://www.openixia.com/userGuides/restPyDoc

Usage:
   # Defaults to Windows
   - Enter: python <script>

   # Connect to Windows Connection Manager
   - Enter: python <script> connection_manager <apiServerIp> <apiServerPort>

   # Connect to Linux API server 
   - Enter: python <script> linux <apiServerIp> <apiServerPort>

"""

import json, sys, os, re, time, datetime, traceback

# Import the RestPy module
from ixnetwork_restpy.testplatform.testplatform import TestPlatform
from ixnetwork_restpy.files import Files

# Set defaults
osPlatform = 'windows'
apiServerIp = '192.168.70.3'
apiServerPort = 11009
username = 'admin'
password = 'admin'

# Allow passing in some params/values from the CLI to replace the defaults
if len(sys.argv) > 1:
    # Command line input:
    #   osPlatform: windows, connection_manager or linux
    osPlatform = sys.argv[1]
    apiServerIp = sys.argv[2]
    apiServerPort = sys.argv[3]

# The IP address for your Ixia license server(s) in a list.
licenseServerIp = ['192.168.70.3']
# subscription, perpetual or mixed
licenseMode = 'subscription'
# tier1, tier2, tier3, tier3-10g
licenseTier = 'tier3'

# For linux and connection_manager only. Set to True to leave the session alive for debugging.
debugMode = False

# Forcefully take port ownership if the portList are owned by other users.
forceTakePortOwnership = True

configFile = 'QuickTestNgpf_vm8.20.ixncfg'

# A list of chassis to use
ixChassisIpList = ['192.168.70.128']
portList = [[ixChassisIpList[0], 1, 1], [ixChassisIpList[0], 2, 1]]

class timestamp:
    """
    Get timestamp for the result files.
    """
    def __init__(self):
        self._get = datetime.datetime.now().strftime('%H%M%S')

    @property
    def get(self):
        return self._get


def verifyQuickTestInitialization(quickTestHandle):
    """
    quickTestHandle = /api/v1/sessions/{id}/ixnetwork/quickTest/rfc2544throughput/{id}
    """
    for timer in range(1,20+1):
        currentAction = getQuickTestCurrentAction(quickTestHandle)
        ixNetwork.info('\n\nverifyQuickTestInitialization currentState: %s' % currentAction)
        if timer < 20:
            if currentAction == 'TestEnded' or currentAction == 'None':
                ixNetwork.info('\n\nverifyQuickTestInitialization CurrentState = %s\n\tWaiting %s/20 seconds to change state\n\n' % (currentAction, timer))
                time.sleep(1)
                continue
            else:
                break

        if timer >= 20:
            if currentAction == 'TestEnded' or currentAction == 'None':
                raise Exception('Quick Test is stuck at TestEnded.')

    ixNetworkVersion = ixNetwork.Globals.BuildNumber
    match = re.match('([0-9]+)\.[^ ]+ *', ixNetworkVersion)
    ixNetworkVersion = int(match.group(1))

    applyQuickTestCounter = 60
    for counter in range(1,applyQuickTestCounter+1):
        quickTestApplyStates = ['InitializingTest', 'ApplyFlowGroups', 'SetupStatisticsCollection']
        currentAction = getQuickTestCurrentAction(quickTestHandle)
        if currentAction == None:
            currentAction = 'ApplyingAndInitializing'

        ixNetwork.info('\n\nverifyQuickTestInitialization: %s  Expecting: TransmittingFrames\n\tWaiting %s/%s seconds\n\n' % (currentAction, counter, applyQuickTestCounter))

        if ixNetworkVersion >= 8:
            if counter < applyQuickTestCounter and currentAction != 'TransmittingFrames':
                time.sleep(1)
                continue

            if counter < applyQuickTestCounter and currentAction == 'TransmittingFrames':
                ixNetwork.info('\n\nVerifyQuickTestInitialization is done applying configuration and has started transmitting frames\n\n')
            break

        if ixNetworkVersion < 8:
            if counter < applyQuickTestCounter and currentAction == 'ApplyingAndInitializing':
                time.sleep(1)
                continue

            if counter < applyQuickTestCounter and currentAction == 'ApplyingAndInitializing':
                ixNetwork.info('\n\nVerifyQuickTestInitialization is done applying configuration and has started transmitting frames\n\n')
            break

        if counter == applyQuickTestCounter:
            if ixNetworkVersion >= 8 and currentAction != 'TransmittingFrames':
                if currentAction == 'ApplyFlowGroups':
                    ixNetwork.info('\n\nIxNetwork is stuck on Applying Flow Groups. You need to go to the session to FORCE QUIT it.\n\n')

                raise Exception('\nVerifyQuickTestInitialization is stuck on %s. Waited %s/%s seconds' % (
                        currentAction, counter, applyQuickTestCounter))

            if ixNetworkVersion < 8 and currentAction != 'Trial':
                raise Exception('\nVerifyQuickTestInitialization is stuck on %s. Waited %s/%s seconds' % (
                    currentAction, counter, applyQuickTestCounter))


def getQuickTestCurrentAction(quickTestHandle):
    """
    quickTestHandle = /api/v1/sessions/{id}/ixnetwork/quickTest/rfc2544throughput/{id}
    """
    ixNetworkVersion = ixNetwork.Globals.BuildNumber
    match = re.match('([0-9]+)\.[^ ]+ *', ixNetworkVersion)
    ixNetworkVersion = int(match.group(1))

    if ixNetworkVersion >= 8:
        timer = 10
        for counter in range(1,timer+1):
            currentActions = quickTestHandle.Results.CurrentActions

            if counter < timer and currentActions == []:
                ixNetwork.info('\n\ngetQuickTestCurrentAction is empty. Waiting %s/%s\n\n' % (counter, timer))
                time.sleep(1)
                continue

            if counter < timer and currentActions != []:
                break

            if counter == timer and currentActions == []:
                raise Exception('\n\ngetQuickTestCurrentActions: Has no action')

        return currentActions[-1]['arg2']
    else:
        return quickTestHandle.Results.Progress


def verifyQuickTestInitialization(quickTestHandle):
    """
    quickTestHandle = /api/v1/sessions/{id}/ixnetwork/quickTest/rfc2544throughput/{id}
    """
    for timer in range(1,20+1):
        currentAction = getQuickTestCurrentAction(quickTestHandle)
        ixNetwork.info('\n\nverifyQuickTestInitialization currentState: %s' % currentAction)
        if timer < 20:
            if currentAction == 'TestEnded' or currentAction == 'None':
                ixNetwork.info('\nverifyQuickTestInitialization CurrentState = %s\n\tWaiting %s/20 seconds to change state\n\n' % (currentAction, timer))
                time.sleep(1)
                continue
            else:
                break

        if timer >= 20:
            if currentAction == 'TestEnded' or currentAction == 'None':
                raise Exception('Quick Test is stuck at TestEnded.')

    ixNetworkVersion = ixNetwork.Globals.BuildNumber
    match = re.match('([0-9]+)\.[^ ]+ *', ixNetworkVersion)
    ixNetworkVersion = int(match.group(1))

    applyQuickTestCounter = 60
    for counter in range(1,applyQuickTestCounter+1):
        quickTestApplyStates = ['InitializingTest', 'ApplyFlowGroups', 'SetupStatisticsCollection']
        currentAction = getQuickTestCurrentAction(quickTestHandle)
        if currentAction == None:
            currentAction = 'ApplyingAndInitializing'

        ixNetwork.info('\nverifyQuickTestInitialization: %s  Expecting: TransmittingFrames\n\tWaiting %s/%s seconds\n\n' % (currentAction, counter, applyQuickTestCounter))

        if ixNetworkVersion >= 8:
            if counter < applyQuickTestCounter and currentAction != 'TransmittingFrames':
                time.sleep(1)
                continue

            if counter < applyQuickTestCounter and currentAction == 'TransmittingFrames':
                ixNetwork.info('\nVerifyQuickTestInitialization is done applying configuration and has started transmitting frames\n\n')

            break

        if ixNetworkVersion < 8:
            if counter < applyQuickTestCounter and currentAction == 'ApplyingAndInitializing':
                time.sleep(1)
                continue

            if counter < applyQuickTestCounter and currentAction == 'ApplyingAndInitializing':
                ixNetwork.info('\nVerifyQuickTestInitialization is done applying configuration and has started transmitting frames\n\n')

            break

        if counter == applyQuickTestCounter:
            if ixNetworkVersion >= 8 and currentAction != 'TransmittingFrames':
                if currentAction == 'ApplyFlowGroups':
                    ixNetwork.info('\nVerifyQuickTestInitialization: IxNetwork is stuck on Applying Flow Groups. You need to go to the session to FORCE QUIT it.\n\n')

                raise Exception('\nVerifyQuickTestInitialization is stuck on %s. Waited %s/%s seconds' % (
                        currentAction, counter, applyQuickTestCounter))

            if ixNetworkVersion < 8 and currentAction != 'Trial':
                raise Exception('\nVerifyQuickTestInitialization is stuck on %s. Waited %s/%s seconds' % (
                        currentAction, counter, applyQuickTestCounter))


def monitorQuickTestRunningProgress(quickTestHandle, getProgressInterval=10):
    """
    Description
        monitor the Quick Test running progress.

    Parameters
        quickTestHandle: /api/v1/sessions/{id}/ixnetwork/quickTest/rfc2544throughput/{id}
    """
    isRunningBreakFlag = 0
    trafficStartedFlag = 0
    waitForRunningProgressCounter = 0
    counter = 1

    while True:
        isRunning = quickTestHandle.Results.IsRunning
        if isRunning == True:
            currentRunningProgress = quickTestHandle.Results.Progress

            if bool(re.match('^Trial.*', currentRunningProgress)) == False:
                if waitForRunningProgressCounter < 30:
                    ixNetwork.info('\n\nisRunning=True. Waiting for trial runs {0}/30 seconds\n\n'.format(waitForRunningProgressCounter))
                    waitForRunningProgressCounter += 1
                    time.sleep(1)

                if waitForRunningProgressCounter == 30:
                    raise Exception('isRunning=True. No quick test stats showing.')
            else:
                trafficStartedFlag = 1
                ixNetwork.info(currentRunningProgress)
                counter += 1
                time.sleep(getProgressInterval)
                continue
        else:
            if trafficStartedFlag == 1:
                # We only care about traffic not running in the beginning.
                # If traffic ran and stopped, then break out.
                ixNetwork.info('\n\nisRunning=False. Quick Test is complete\n\n')
                return 0

            if isRunningBreakFlag < 20:
                ixNetwork.info('\n\nisRunning=False. Wait {0}/20 seconds\n\n'.format(isRunningBreakFlag))
                isRunningBreakFlag += 1
                time.sleep(1)
                continue

            if isRunningBreakFlag == 20:
                raise Exception('Quick Test failed to start:', response.json()['status'])


def copyFileWindowsToLocalWindows(windowsPathAndFileName, localPath, includeTimestamp=False):
    """
    Description
        Copy files from the Windows IxNetwork API Server to a local c: drive destination.
        You could include a timestamp for the destination file.

    Parameters
        windowsPathAndFileName: (str): The full path and filename to retrieve from Windows client.
        localPath: (str): The Windows local path without the filename. Ex: C:\\Results.
        includeTimestamp: (bool):  If False, each time you copy the same file will be overwritten.

    Example:
       WindowsPathAndFileName =  'C:\\Users\\hgee\\AppData\\Local\\Ixia\\IxNetwork\\data\\result\\DP.Rfc2544Tput\\9e1a1f04-fca5-42a8-b3f3-74e5d165e68c\\Run0001\\TestReport.pdf'
       localPath = 'C:\\Results'
    """
    ixNetwork.info('\n\ncopyFileWindowsToLocalWindows: From: %s to %s\n\n' % (windowsPathAndFileName, localPath))
    fileName = windowsPathAndFileName.split('\\')[-1]
    fileName = fileName.replace(' ', '_')
    if includeTimestamp:
        fileName = addTimestampToFile(fileName)

    destinationPath = localPath+'\\'+fileName
    ixNetwork.info('\nCopying from {} -> {}'.format(windowsPathAndFileName, destinationPath))
    ixNetwork.CopyFile(windowsPathAndFileName, destinationPath)


def copyApiServerFileToLocalLinux(apiServerPathAndFileName, localPath, localPathOs='linux', includeTimestamp=False):
    """
    Description
        Copy files from either a Windows or Linux API Server to a local Linux filesystem.
        The source path could be any path in the API server.
        The filename to be copied will remain the same filename unless you set renameDestinationFile to something else.
        You could also append a timestamp for the destination file so the result files won't be overwritten.

    Parameters
        apiServerPathAndFileName: (str): The full path and filename to retrieve from either a Windows API server or a Linux API server.
        localPath: (str): The Linux local filesystem path without the filename. Ex: /home/hgee/Results.
        localPathOs: (str): The destination's OS.  linux or windows.
        includeTimestamp: (bool):  If False, each time you copy the same file will be overwritten.

    Example:
       apiServerPathAndFileName =  '/root/.local/share/Ixia/IxNetwork/data/result/DP.Rfc2544Tput/10694b39-6a8a-4e70-b1cd-52ec756910c3/Run0005/portMap.csv'
       localPath = '/home/hgee/portMap.csv'
    """
    if '/' in apiServerPathAndFileName:
        fileName = apiServerPathAndFileName.split('/')[-1]

    if '\\' in apiServerPathAndFileName:
        fileName = apiServerPathAndFileName.split('\\')[-1]

    fileName = fileName.replace(' ', '_')

    if includeTimestamp:
        fileName = addTimestampToFile(fileName)

    if localPathOs == 'linux':
        destinationPath = localPath+'/'+fileName

    if localPathOs == 'windows':
        destinationPath = localPath+'\\'+fileName

    ixNetwork.info('\nCopying file from API server:{} -> {}'.format(apiServerPathAndFileName, destinationPath))
    session.DownloadFile(apiServerPathAndFileName, destinationPath)


def getQuickTestCsvFiles(quickTestHandle, copyToPath, csvFile='all', includeTimestamp=False):
    """
    Description
        Copy Quick Test CSV result files to a specified path on either Windows or Linux.
        Note: Currently only supports copying from Windows.
              Copy from Linux is coming in November.

    quickTestHandle: The Quick Test handle.
    copyToPath: The destination path to copy to.
                If copy to Windows: Ex:  c:\\Results\\Path
                If copy to Linux:   Ex:  /home/user1/results/path

    csvFile: A list of CSV files to get: 'all', one or more CSV files to get:
             AggregateResults.csv, iteration.csv, results.csv, logFile.txt, portMap.csv
    includeTimestamp: To append a timestamp on the result file.
    """
    resultsPath = quickTestHandle.Results.ResultPath
    ixNetwork.info('\ngetQuickTestCsvFiles: %s' % resultsPath)

    if csvFile == 'all':
        getCsvFiles = ['AggregateResults.csv', 'iteration.csv', 'results.csv', 'logFile.txt', 'portMap.csv']
    else:
        if type(csvFile) is not list:
            getCsvFiles = [csvFile]
        else:
            getCsvFiles = csvFile

    for eachCsvFile in getCsvFiles:
        # Backslash indicates the results resides on a Windows OS.
        if '\\' in resultsPath:
            windowsSource = resultsPath+'\\{0}'.format(eachCsvFile)

            if bool(re.match('[a-z]:.*', copyToPath, re.I)):
                copyFileWindowsToLocalWindows(windowsSource, copyToPath, includeTimestamp=includeTimestamp)
            else:
                # Copy From Windows API server to local Linux client filesystem
                copyApiServerFileToLocalLinux(windowsSource, copyToPath, localPathOs='linux', includeTimestamp=includeTimestamp)

        else:
            linuxSource = resultsPath+'/{0}'.format(eachCsvFile)

            # Copy from Linux api server to Local Linux client filesystem.
            try:
                ixNetwork.info('\nCopying file from Linux API server:{} to local Linux:{}'.format(linuxSource, eachCsvFile))
                copyApiServerFileToLocalLinux(linuxSource, copyToPath, localPathOs='linux', includeTimestamp=includeTimestamp)

            except Exception as errMsg:
                print('copyApiServerFileToLocalLinux ERROR:', errMsg)


def addTimestampToFile(filename):
    """
    Add a timestamp to a file to avoid overwriting existing files.

    If a path is included, it will yank out the file from the path.
    """
    currentTimestamp = timestamp.get
    if '\\' in filename:
        filename = filename.split('\\')[-1]

    if '/' in filename:
        filename = filename.split('/')[-1]

    newFilename = filename.split('.')[0]
    newFileExtension = filename.split('.')[1]
    newFileWithTimestamp = '{}_{}.{}'.format(newFilename, currentTimestamp,  newFileExtension)
    return newFileWithTimestamp


try:
    testPlatform = TestPlatform(apiServerIp, rest_port=apiServerPort, platform=osPlatform, log_file_name='restpy.log')

    # Console output verbosity: None|request|'request response'
    testPlatform.Trace = 'request_response'

    testPlatform.Authenticate(username, password)
    session = testPlatform.Sessions.add()
    ixNetwork = session.Ixnetwork

    ixNetwork.NewConfig()
    ixNetwork.LoadConfig(Files(configFile, local_file=True))

    ixNetwork.Globals.Licensing.LicensingServers = licenseServerIp
    ixNetwork.Globals.Licensing.Mode = licenseMode
    ixNetwork.Globals.Licensing.Tier = licenseTier

    # Assign ports
    testPorts = []
    vportList = [vport.href for vport in ixNetwork.Vport.find()]
    for port in portList:
        testPorts.append(dict(Arg1=port[0], Arg2=port[1], Arg3=port[2]))

    ixNetwork.AssignPorts(testPorts, [], vportList, forceTakePortOwnership)

    quickTestHandle = ixNetwork.QuickTest.Rfc2544throughput.find(Name='QuickTest1')
    quickTestHandle.Apply()
    quickTestHandle.Start()
    verifyQuickTestInitialization(quickTestHandle)
    monitorQuickTestRunningProgress(quickTestHandle)

    # Create a timestamp for test result files.
    # To append a timestamp in the CSV result files so existing result files won't get overwritten.
    timestamp = timestamp()

    # Copy CSV files from Windows to same windows drive
    getQuickTestCsvFiles(quickTestHandle, copyToPath='c:\\Results', includeTimestamp=True)

    # Copy CSV from either a Windows or Linux API server to local linux filesystem
    getQuickTestCsvFiles(quickTestHandle, copyToPath='.', includeTimestamp=True)

    pdfFile = quickTestHandle.GenerateReport()
    
    # Copying the PDF from Windows to local Windows.
    copyFileWindowsToLocalWindows(pdfFile, 'c:\\Results')

    # Copying PDF from either a Windows API server or from a Linux API server to local Linux filesystem.
    destPdfTestResult = addTimestampToFile(pdfFile)
    session.DownloadFile(pdfFile, './'+destPdfTestResult)

    quickTestHandle.Stop()
    quickTestHandle.remove()

    if debugMode == False:
        # For Linux and Windows Connection Manager only
        session.remove()

except Exception as errMsg:
    print('\n%s' % traceback.format_exc())
    if debugMode == False and 'session' in locals():
        session.remove()





