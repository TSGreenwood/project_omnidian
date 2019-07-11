
# Creating an anomaly detection model


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

Prepare a dataset of "smooth and stable" exemplars


```python
try:
    conn = get_db_connection()
    data = pd.read_sql("SELECT pr.asset_id, pr.date, pr.prt1, pr.prt7 " +
        "FROM omnidian.performance_ratio pr " +
        "INNER JOIN " +
        "(SELECT asset_id, COUNT(prt7) AS num, STDDEV_POP(prt7) AS sd " +
        "FROM omnidian.performance_ratio " +
        "WHERE DATE >= '2017-01-01' AND DATE <= '2017-12-31' " +
        "GROUP BY asset_id) tab ON pr.asset_id = tab.asset_id " +
        "WHERE tab.num = 365 AND tab.sd < 0.10 AND tab.sd > 0.0 AND pr.date >= '2017-01-01' AND pr.date <= '2017-12-31' " +
        "ORDER BY pr.asset_id, pr.date",
                       con=conn, parse_dates=['date']).set_index(['asset_id', 'date'])
finally:
    conn.close()
```


```python
shingle(data.loc[101111456].prt7, 7)
```




    array([[1.1729, 1.1878, 1.2009, ..., 1.1978, 1.1922, 1.1879],
           [1.1878, 1.2009, 1.2026, ..., 1.1922, 1.1879, 1.0841],
           [1.2009, 1.2026, 1.1978, ..., 1.1879, 1.0841, 1.0816],
           ...,
           [1.086 , 1.0885, 1.0966, ..., 1.0605, 1.0681, 1.041 ],
           [1.0885, 1.0966, 1.0667, ..., 1.0681, 1.041 , 1.0172],
           [1.0966, 1.0667, 1.0605, ..., 1.041 , 1.0172, 1.0139]])




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
asset_ids = data.index.get_level_values(0).unique().tolist()
```


```python
shingles = None
for assetId in asset_ids:
    newShingles = shingle(data.loc[assetId].prt7, shingle_length)
    if shingles is None:
        shingles = newShingles
    else:
        shingles = np.concatenate((shingles, newShingles))
```


```python
shingles
```




    array([[1.1729, 1.1878, 1.2009, ..., 1.1978, 1.1922, 1.1879],
           [1.1878, 1.2009, 1.2026, ..., 1.1922, 1.1879, 1.0841],
           [1.2009, 1.2026, 1.1978, ..., 1.1879, 1.0841, 1.0816],
           ...,
           [0.8102, 0.8431, 0.8458, ..., 0.8676, 0.8757, 0.8787],
           [0.8431, 0.8458, 0.8628, ..., 0.8757, 0.8787, 0.8758],
           [0.8458, 0.8628, 0.8676, ..., 0.8787, 0.8758, 0.8496]])




```python
rcf = RandomCutForest(role=role,
                      train_instance_count=1,
                      train_instance_type='ml.m4.xlarge',
                      data_location='s3://{}/{}/'.format(bucket, prefix),
                      output_path='s3://{}/{}/output'.format(bucket, prefix),
                      num_samples_per_tree=365,
                      num_trees=300)
rcf.fit(rcf.record_set(shingles))
```

### Deploy a new endpoint from the most-recently-trained model


```python
from sagemaker.predictor import csv_serializer, json_deserializer

rcf_inference = rcf.deploy(
    initial_instance_count=1,
    instance_type='ml.m4.xlarge',
)

rcf_inference.content_type = 'text/csv'
rcf_inference.serializer = csv_serializer
rcf_inference.accept = 'appliation/json'
rcf_inference.deserializer = json_deserializer
```

    INFO:sagemaker:Creating model with name: randomcutforest-2018-12-17-21-59-59-536
    INFO:sagemaker:Creating endpoint with name randomcutforest-2018-12-17-21-54-56-793


    ---------------------------------------------------------------------------------------!


```python
def write_dicts_to_file(path, data):
    with open(path, 'wb') as fp:
        for d in data:
            fp.write(json.dumps(d).encode("utf-8"))
            fp.write("\n".encode('utf-8'))

write_dicts_to_file("train.json", training_data)
write_dicts_to_file("test.json", test_data)

```


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
copy_to_s3("train.json", "{}/train/train.json".format(s3_data_path), override=True)
copy_to_s3("test.json", "{}/test/test.json".format(s3_data_path), override=True)
```
