
## Anomaly detection with Random Cut Forests


```python
!conda install -y mysql-connector-python
```

    Solving environment: done
    
    
    ==> WARNING: A newer version of conda exists. <==
      current version: 4.5.11
      latest version: 4.5.12
    
    Please update conda by running
    
        $ conda update -n base -c defaults conda
    
    
    
    # All requested packages already installed.
    



```python
import sagemaker
import boto3
from botocore.exceptions import ClientError
import json
import base64
import mysql.connector
import pandas as pd
import s3fs
import matplotlib.pyplot as plt
import numpy as np
import datetime
import itertools

role = sagemaker.get_execution_role()
session = sagemaker.Session()
region = session.boto_region_name

```


```python
bucket = "omnidian-sagemaker-experiment"
prefix = "anomalies"
```


```python
def get_db_connection():
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name='us-east-1')
    try:
        response = client.get_secret_value(SecretId='prod-rds-read-write')
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("The requested secret {} was not found".format(secret_name))
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            print("The request was invalid due to {}".format(e))
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            print("The request had invalid params: {}".format(e))
    else:
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
        else:
            secret = base64.b64decode(response['SecretBinary'])
    connection = mysql.connector.connect(user=secret['username'], password=secret['password'], host=secret['host'])
    return connection
```


```python
def shingle(data, shingle_size):
    num_data = len(data)
    shingled_data = np.zeros((num_data-shingle_size+1, shingle_size))
    
    for n in range(num_data - shingle_size + 1):
        shingled_data[n] = data[n:(n+shingle_size)]
    return shingled_data

shingle_length = 7
```

### Deploy a new endpoint from a stored model


```python
from sagemaker.predictor import csv_serializer, json_deserializer

rcf_inference = sagemaker.RandomCutForestPredictor('AnomalyPredictor', session)

rcf_inference.content_type = 'text/csv'
rcf_inference.serializer = csv_serializer
rcf_inference.accept = 'appliation/json'
rcf_inference.deserializer = json_deserializer
```


```python
try:
    conn = get_db_connection()
    all_data = pd.read_sql("SELECT pr.asset_id, pr.date, pr.prt7, ahd.health_status " +
        "FROM omnidian.performance_ratio pr " +
        "INNER JOIN omnidian.asset_health_daily ahd " +
        "ON pr.asset_id = ahd.asset_id AND pr.date = ahd.date " +
        "WHERE ahd.date >= '2016-01-01' AND ahd.date <= '2018-12-31' " +
        "ORDER BY pr.asset_id, pr.date",
                       con=conn, parse_dates=['date']).set_index(['asset_id', 'date'])
finally:
    conn.close()
```

We can process a set of data by dividing it into a set of overlapping shingles and scoring each of the shingles. The set of scores can then be analysed to find outliers.


```python
def doStats(scores):
    # compute the shingled score distribution and cutoff and determine anomalous scores
    score_mean = scores.mean()
    score_std = scores.std()
    score_cutoff = score_mean + 4*score_std

    anomalies = scores[scores > score_cutoff]
    return (score_cutoff, anomalies)
    
def process(input_data):
    results = rcf_inference.predict(shingle(input_data.prt7, shingle_length))
    scores = pd.Series([datum['score'] for datum in results['scores']], input_data.index[:-6])
    (score_cutoff, anomalies) = doStats(scores)
    
    data = input_data.loc[anomalies.index]
    data['score'] = anomalies
    
    return (score_cutoff, data)
```

To examine incoming data, we can score each day as the *end* of a shingle, and build up a set of scores over time. These scores can be analysed in a similar manner to the process above. If the latest shingle scores as an outlier, we've detected an anomaly at the "live" end of the stream.

To simulate this process on historical data, we take a shortcut: we shingle the entire historical dataset, and score it all at once. Then we slide a window over the data and the scores, to simulate what we'd be able to see at each day's processing. If we find the "current day" is anomalous, we record it for output.

Note that the scores we have to consider are 6 fewer than the sliding window over the data. This represents the fact that the "current day" is at the end of the shingle labeled six days prior, and so those last six scores are for shingles including days that "haven't happened yet" -- and thus must be excluded from the statistical analysis.


```python
def scan(assetID):
    assetData = all_data.loc[assetID]
    results = {}
    scoringResults = rcf_inference.predict(shingle(assetData.prt7, shingle_length))
    scores = pd.Series([datum['score'] for datum in scoringResults['scores']], assetData.index[:-6])
    for i in range(365*2):
        input_data = assetData.iloc[i:366+i]
        (score_cutoff, anomalies) = doStats(scores.iloc[i:360+i])
        if (input_data.index[-7] in anomalies.index) and (input_data.iloc[-1].health_status != 'Unknown'):
            results[input_data.index[-1]] = (input_data.iloc[-1].prt7, input_data.iloc[-1].health_status)
    return results
```


```python
d = [datetime.date(2017,1,1), datetime.date(2017,1,2), datetime.date(2017,1,3), datetime.date(2017,1,4), datetime.date(2017,2,3), datetime.date(2017,2,4), datetime.date(2017,2,6)]
```


```python
def findSpans(seq):
    result = []
    current = ()
    for item in seq:
        if len(current) == 0:
            current = (item, item)
        elif item == current[-1] + datetime.timedelta(days=1):
            current = (current[0], item)
        else:
            result.append(list(map(str, current)))
            current = (item, item)
    if len(current) > 0:
        result.append(list(map(str, current)))
    return result

findSpans(d)
```




    [['2017-01-01', '2017-01-04'],
     ['2017-02-03', '2017-02-04'],
     ['2017-02-06', '2017-02-06']]




```python
all_asset_ids = all_data.index.get_level_values(0).unique().tolist()
```


```python
with open("101anomalies.json", 'wb') as fp:
    for assetID in all_asset_ids:
        try:
            dates = set()
            anomalies = scan(assetID)
            for item in anomalies.keys():
                for offset in range(7):
                    dates.add(item.date() - datetime.timedelta(days=offset))
            dateList = list(dates)
            dateList.sort()
            fp.write("{{'{assetID}': {days}}}".format(assetID=assetID, days=findSpans(dateList)).encode("utf-8"))
            fp.write("\n".encode('utf-8'))
            print('.', end='')
        except KeyboardInterrupt:
            break
        except:
            pass

```

    ................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................


```python
s3 = boto3.resource('s3')
def copy_to_s3(local_file, s3_path, override=False):
    assert s3_path.startswith('s3://')
    split = s3_path.split('/')
    bucket = split[2]
    path = '/'.join(split[3:])
    buk = s3.Bucket(bucket)
    
    if len(list(buk.objects.filter(Prefix=path))) > 0:
        if not override:
            print('File s3://{}/{} already exists.\nSet override to upload anyway.\n'.format(s3_bucket, s3_path))
            return
        else:
            print('Overwriting existing file')
    with open(local_file, 'rb') as data:
        print('Uploading file to {}'.format(s3_path))
        buk.put_object(Key=path, Body=data)
```


```python
def write_dicts_to_file(path, data):
    with open(path, 'wb') as fp:
        for d in data:
            fp.write("<a target='_new' href='https://resolv.omnidian.com/Solar/AssetDetails/{0}'>{0}</a>\n".format(d).encode("utf-8"))
            fp.write("\n".encode('utf-8'))
```


```python
write_dicts_to_file('101anom.html', frames)
```


```python

```
