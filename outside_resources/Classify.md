
# Using a trained model to classify samples


```python
!conda install -y mysql-connector-python
```

    Solving environment: done
    
    
    ==> WARNING: A newer version of conda exists. <==
      current version: 4.5.11
      latest version: 4.6.2
    
    Please update conda by running
    
        $ conda update -n base -c defaults conda
    
    
    
    ## Package Plan ##
    
      environment location: /home/ec2-user/anaconda3/envs/python3
    
      added / updated specs: 
        - mysql-connector-python
    
    
    The following packages will be downloaded:
    
        package                    |            build
        ---------------------------|-----------------
        mysql-connector-c-6.1.11   |       hf4847fb_0         4.4 MB
        mysql-connector-python-8.0.13|   py36h9c95fcb_0         689 KB
        ca-certificates-2018.12.5  |                0         123 KB
        ------------------------------------------------------------
                                               Total:         5.2 MB
    
    The following NEW packages will be INSTALLED:
    
        mysql-connector-c:      6.1.11-hf4847fb_0                
        mysql-connector-python: 8.0.13-py36h9c95fcb_0            
    
    The following packages will be UPDATED:
    
        ca-certificates:        2018.8.24-ha4d7672_0  conda-forge --> 2018.12.5-0      
        certifi:                2018.8.24-py36_1      conda-forge --> 2018.11.29-py36_0
        libstdcxx-ng:           7.2.0-hdf63c60_3                  --> 8.2.0-hdf63c60_1 
        openssl:                1.0.2p-h470a237_0     conda-forge --> 1.0.2p-h14c3975_0
    
    
    Downloading and Extracting Packages
    mysql-connector-c-6. | 4.4 MB    | ##################################### | 100% 
    mysql-connector-pyth | 689 KB    | ##################################### | 100% 
    ca-certificates-2018 | 123 KB    | ##################################### | 100% 
    Preparing transaction: done
    Verifying transaction: done
    Executing transaction: done



```python
import io
import json
import boto3
import base64
import s3fs
import random
import math
import csv
import time
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
from botocore.exceptions import ClientError

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

def get_asset_data(conn, asset_id, from_date, to_date):
    return pd.read_sql("SELECT pr.date, DAYOFYEAR(pr.date) as doy, pr.prt1, pr.prt7, pr.prt365, prb.prt7 as lag_prt7, prb.prt365 as lag_prt365, ad.energy " + 
        "FROM performance_ratio pr " +
        "LEFT JOIN actual_daily ad ON pr.asset_id = ad.asset_id AND pr.date = ad.date " +
        "LEFT JOIN performance_ratio prb ON pr.asset_id = prb.asset_id AND pr.date = DATE_ADD(prb.date, INTERVAL 1 YEAR) " +
        "WHERE pr.date >= '{0}' AND pr.date <= '{1}' ".format(from_date.isoformat(), to_date.isoformat()) +
        "AND pr.asset_id = {0} ".format(asset_id) +
        "ORDER BY pr.date DESC", 
        con=conn, parse_dates=['date']).set_index(['date'])

def get_asset_status(conn):
    return pd.read_sql("SELECT asset_id, date AS last_date, health_status, days FROM days_in_state", 
        con=conn, parse_dates=['last_date'])

def create_libsvm_row(values):
    return ' '.join(["{0}:{1:0.5}".format(index, item) for (index, item) in zip(range(len(values)), values) if not np.isnan(item)])

```

## Generating sample data for inference

First set up the enumeration of databases and filenames


```python
dbs = ['omnidian'] # , 'omnidian_102', 'omnidian_104', 'omnidian_105', 'omnidian_106', 'omnidian_107', 'omnidian_108', 'omnidian_109', 'omnidian_112']
sample_length = 28

def create_sample(data):
    first_element = data.iloc[0].fillna(-1.0)
    values = [float(first_element.doy), float(first_element.prt365), float(first_element.lag_prt365)]
    values.extend(data.prt1.fillna(-1.0).tolist())
    return values
```

Prepare for inference


```python
labels = ['No problem', 'Shading', 'Inverter problem', 'String problem', 'Soiling', 'Weather', 'Missing data', 'Other']
runtime_client = boto3.client('runtime.sagemaker')
client = boto3.client('sagemaker')
endpoint_config = 'Logistic-RC-1-config'
endpoint = 'Logistic-RC-1-endpoint'
csvfile = 'results-13FEB.csv'
```


```python
arn = client.create_endpoint(EndpointName=endpoint, EndpointConfigName=endpoint_config)['EndpointArn']
print('Creating endpoint', endpoint, 'with ARN', arn)
status = client.describe_endpoint(EndpointName=endpoint)['EndpointStatus']
while(status != 'InService'):
    print('...', end=' ')
    time.sleep(10)
    status = client.describe_endpoint(EndpointName=endpoint)['EndpointStatus']
print()
print('Endpoint in service')
```

    Creating endpoint Logistic-RC-1-endpoint with ARN arn:aws:sagemaker:us-east-1:202172962406:endpoint/logistic-rc-1-endpoint
    ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... ... 
    Endpoint in service


Run each dataset against the model. For each result, check if it's an "interesting" one, then filter for trivial inputs ("obvious problems"). Report on what's left.


```python
try:
    conn = get_db_connection()
    with open(csvfile, 'w', newline='') as outp: 
        csvoutp = csv.writer(outp, dialect='excel')
        csvoutp.writerow(['asset_id', 'label', 'current_health', 'days_in_state'])
        for db in dbs:
            print('Processing', db)
            conn.database = db
            asset_status = get_asset_status(conn).set_index(['asset_id'])
            for (asset_id, current) in asset_status.iterrows():
                end = datetime.date(2019, 2, 13) # current.last_date.date()
                start = end - datetime.timedelta(days=sample_length)
                data = get_asset_data(conn, asset_id, start, end)
                if not np.all(np.isnan(data.prt1.fillna(np.nan))):
                    row = create_libsvm_row(create_sample(data))
                    response = runtime_client.invoke_endpoint(EndpointName=endpoint, ContentType='text/x-libsvm', Body=row)
                    result = math.floor(float(response['Body'].read().decode('ascii')))
                    conn.cmd_query("INSERT INTO ml_labels (asset_id, date, label) VALUES ({0}, '{1}', '{2}') ON DUPLICATE KEY UPDATE label=VALUES(label)".format(
                        asset_id, end.isoformat(), labels[result]))
                    if result in [1,2,3,4] and not ((current.health_status == 'ZeroGen' or current.health_status == 'NonCom') and current.days > sample_length-1):
                        print(asset_id, labels[result], '-', current.health_status, 'for', current.days, 'days')
                    csvoutp.writerow([asset_id, labels[result], current.health_status, current.days])
            conn.commit()
finally:
    conn.close()
    print(' -- END --')
```

    Processing omnidian
    101111454 Inverter problem - ZeroGen for 2 days
    101111455 Inverter problem - UnderProducing for 10 days
    101111464 Inverter problem - Healthy for 1 days
    101111481 Shading - ZeroGen for 1 days
    101111510 Inverter problem - ZeroGen for 2 days
    101111517 Inverter problem - ZeroGen for 2 days
    101111537 Inverter problem - ZeroGen for 2 days
    101111558 Inverter problem - ZeroGen for 2 days
    101111625 Shading - UnderProducing for 146 days
    101111683 Inverter problem - UnderProducing for 64 days
    101111791 Inverter problem - ZeroGen for 14 days
    101111819 Shading - UnderProducing for 16 days
    101111850 Inverter problem - ZeroGen for 19 days
    101111948 Inverter problem - UnderProducing for 41 days
    101111957 Shading - UnderProducing for 41 days
    101112032 Shading - UnderProducing for 64 days
    101112036 Inverter problem - UnderProducing for 41 days
    101112070 Inverter problem - UnderProducing for 64 days
    101112121 Inverter problem - UnderProducing for 1 days
    101112164 Inverter problem - NonCom for 5 days
    101112199 Inverter problem - NonCom for 13 days
    101112215 Shading - UnderProducing for 64 days
    101112230 Inverter problem - UnderProducing for 5 days
    101112442 Shading - OverProducing for 39 days
    101112466 Shading - UnderProducing for 2 days
    101112534 Inverter problem - ZeroGen for 10 days
    101112567 Shading - UnderProducing for 64 days
    101112600 Inverter problem - UnderProducing for 41 days
    101112602 Inverter problem - UnderProducing for 4 days
    101112642 Inverter problem - ZeroGen for 2 days
    101112663 Shading - UnderProducing for 41 days
    101112716 Shading - UnderProducing for 41 days
    101112805 Inverter problem - UnderProducing for 31 days
    101112808 Inverter problem - NonCom for 1 days
    101112821 Inverter problem - UnderProducing for 41 days
    101112847 Inverter problem - UnderProducing for 2 days
    101112888 Inverter problem - ZeroGen for 2 days
    101112895 Inverter problem - ZeroGen for 1 days
    101112911 Shading - UnderProducing for 22 days
    101112936 Inverter problem - Healthy for 8 days
    101112938 Inverter problem - ZeroGen for 18 days
    101112999 Inverter problem - UnderProducing for 41 days
    101113005 Inverter problem - UnderProducing for 41 days
    101113025 Inverter problem - UnderProducing for 1 days
    101113028 Inverter problem - ZeroGen for 1 days
    101113031 Inverter problem - UnderProducing for 1 days
    101113043 Inverter problem - ZeroGen for 19 days
    101113056 Inverter problem - UnderProducing for 10 days
    101113073 Shading - UnderProducing for 41 days
    101113079 Inverter problem - UnderProducing for 40 days
    101113094 Inverter problem - ZeroGen for 24 days
    101113118 Inverter problem - ZeroGen for 12 days
    101113262 Inverter problem - NonCom for 12 days
    101113274 Inverter problem - UnderProducing for 41 days
    101113303 Inverter problem - UnderProducing for 41 days
    101113328 Shading - UnderProducing for 41 days
    101113450 Inverter problem - UnderProducing for 40 days
    101113465 Inverter problem - ZeroGen for 1 days
     -- END --



    ---------------------------------------------------------------------------

    TypeError                                 Traceback (most recent call last)

    <ipython-input-23-66181dcd4b75> in <module>()
         12                 start = end - datetime.timedelta(days=sample_length)
         13                 data = get_asset_data(conn, asset_id, start, end)
    ---> 14                 if not np.all(np.isnan(data.prt1.fillna(np.nan))):
         15                     row = create_libsvm_row(create_sample(data))
         16                     response = runtime_client.invoke_endpoint(EndpointName=endpoint, ContentType='text/x-libsvm', Body=row)


    TypeError: ufunc 'isnan' not supported for the input types, and the inputs could not be safely coerced to any supported types according to the casting rule ''safe''



```python
client.delete_endpoint(EndpointName=endpoint)
```




    {'ResponseMetadata': {'RequestId': '309d0b64-4982-41e1-8c6d-227575177cc2',
      'HTTPStatusCode': 200,
      'HTTPHeaders': {'x-amzn-requestid': '309d0b64-4982-41e1-8c6d-227575177cc2',
       'content-type': 'application/x-amz-json-1.1',
       'content-length': '0',
       'date': 'Fri, 15 Feb 2019 03:38:09 GMT'},
      'RetryAttempts': 0}}




```python

```
