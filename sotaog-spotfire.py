import json
import time
import traceback

from Spotfire.Dxp.Framework.ApplicationModel import ProgressService
from Spotfire.Dxp.Data import AddRowsSettings, DataValueCursor, DataType
from Spotfire.Dxp.Data.Import import TextDataReaderSettings, TextFileDataSource
from System.IO import MemoryStream, SeekOrigin, StreamReader, StreamWriter
from System.Net import HttpWebRequest
from System.Text import Encoding

def login():
    global accessToken

    requestBody = 'grant_type=client_credentials&scope=ata-administrator+ata-technician'
    url = baseUrl + '/authenticate'
    webRequest = HttpWebRequest.Create(url)
    webRequest.Method = 'POST'
    webRequest.ContentType = 'application/x-www-form-urlencoded'
    webRequest.Headers.Add('Authorization', 'Basic ' + credentials)
    bytes = Encoding.ASCII.GetBytes(requestBody)
    webRequest.ContentLength = bytes.Length
    requestStream = webRequest.GetRequestStream()
    requestStream.Write(bytes, 0, bytes.Length)
    requestStream.Close()

    response = webRequest.GetResponse()

    jsonString = StreamReader(response.GetResponseStream()).ReadToEnd()
    data = json.loads(jsonString)
    accessToken = data['access_token']
    print 'accessToken', accessToken
    return accessToken

def apiRequest(relativeUrl):
    url = baseUrl + relativeUrl
    print 'calling url ' + url
    request = HttpWebRequest.Create(url)
    request.Method = 'GET'
    request.Accept = 'application/json'
    request.Headers.Add('Authorization', 'Bearer ' + accessToken)
    response = request.GetResponse()
    data = json.loads(StreamReader(response.GetResponseStream()).ReadToEnd())
    return data

def jsonToCSV(data, columns):
    # format json to csv
    csv = ','.join(columns) + '\n'
    for row in data:
        csv += ','.join(str(row[col]) for col in columns) + '\n'
    return csv

def csvToDataSource(csv, columnDataTypes):
    # Create memorystream to read from
    stream = MemoryStream()
    writer = StreamWriter(stream)
    writer.Write(csv)
    writer.Flush()
    stream.Seek(0, SeekOrigin.Begin)

    # Create text file data source
    readerSettings = TextDataReaderSettings()
    readerSettings.Separator = ','
    readerSettings.AddColumnNameRow(0)
    print 'columnDataTypes ', columnDataTypes
    for i, columnDataType in enumerate(columnDataTypes):
        readerSettings.SetDataType(i, columnDataType)

    dataSource = TextFileDataSource(stream, readerSettings)
    dataSource.ReuseSettingsWithoutPrompting = True
    dataSource.IsPromptingAllowed = False
    return dataSource

def formatDatapoints(data, assetId):
    formattedData = []
    for datatype in data:
        for row in data[datatype]:
            newRow = {
                'asset_id': assetId,
                'datatype': datatype,
                'timestamp': row[0],
                'value': row[1]
            }
            formattedData.append(newRow)
    return formattedData

def updateAssetTable(assetType, columns, columnDataTypes):
    # fetch the assets from the API
    data = apiRequest('/' + assetType)
    print 'first row {}'.format(data[0])
    csv = jsonToCSV(data, columns)
    dataSource = csvToDataSource(csv, columnDataTypes)
    
    # Replace the table data
    if Document.Data.Tables.Contains(assetType):
        Document.Data.Tables[assetType].ReplaceData(dataSource)
    else:
        Document.Data.Tables.Add(assetType, dataSource)


def updateDatapointTable(assetType):
    assetTable = Document.Data.Tables[assetType]
    idColumn = DataValueCursor.Create[str](assetTable.Columns['id'])

    ps.CurrentProgress.BeginSubtask('Loading datapoints for ' + assetType, assetTable.RowCount, 'Step {0} of {1}')
    for row in assetTable.GetRows(idColumn):
        datapointTableName = assetType + '_datapoints'
        datapointTable = None

        # Default start date or max value from table
        startDate = defaultStartTimestamp
        if Document.Data.Tables.Contains(datapointTableName):
            datapointTable = Document.Data.Tables[datapointTableName]
            assetRowSelection = datapointTable.Select('asset_id = "{}"'.format(idColumn.CurrentValue))
            if not assetRowSelection.IsEmpty:
                startDate = datapointTable.Columns['timestamp'].RowValues.GetMaxValue(assetRowSelection.AsIndexSet()).Value

        print 'calculated startDate', startDate
        url = '/datapoints/{}?limit={}&start_ts={}&sort=asc'.format(idColumn.CurrentValue, 4320, startDate)
        data = apiRequest(url)
        # format datapoint data
        data = formatDatapoints(data, idColumn.CurrentValue)
        csv = jsonToCSV(data, ['asset_id', 'datatype', 'timestamp', 'value'])
        dataSource = csvToDataSource(csv, [DataType.String, DataType.String, DataType.LongInteger, DataType.Real])

        
        if Document.Data.Tables.Contains(datapointTableName):
            settings = AddRowsSettings(datapointTable, dataSource)
            datapointTable.AddRows(dataSource, settings)
        else:
            Document.Data.Tables.Add(datapointTableName, dataSource)
        ps.CurrentProgress.TryReportProgress()

def updateData():
    global accessToken

    try:
        ps.CurrentProgress.ExecuteSubtask('Login')
        accessToken = login()
        ps.CurrentProgress.ExecuteSubtask('Loading Wells')
        updateAssetTable('wells', ['id', 'asset_type', 'label'], [DataType.String, DataType.String, DataType.String])
        ps.CurrentProgress.ExecuteSubtask('Loading Well Datapoints')
        updateDatapointTable('wells')
    except Exception as e:
        print 'exception', e
        traceback.print_exc()
        pass


ps = Application.GetService[ProgressService]()
ps.ExecuteWithProgress('Update data', 'Updates all tables', updateData)


