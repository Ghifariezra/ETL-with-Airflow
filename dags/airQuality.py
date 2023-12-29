from airflow import DAG
from airflow.operators.python_operator import PythonOperator, BranchPythonOperator
from airflow.operators.postgres_operator import PostgresOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.edgemodifier import Label
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
from psycopg2 import errors

""" ETL PROCESS """
# TODO 1: Extract
def fetch_urlCities(**kwargs):
    import requests as req
    
    """ Initialize Task Instance """
    ti = kwargs['ti']

    """ Initialize Result Params """
    url = kwargs['url']
    params = kwargs['params']
    headers = kwargs['headers']

    """ EXTRACTION """
    response = req.get(
        url=url,
        params=params,
        headers=headers)
    
    data = response.json()
    statusResponse = response.status_code

    if statusResponse != 200:
        return f'{statusResponse} - {response.reason}'
    else:
        """ FILTERING DATA """
        try:
            results = data['results'][0]

            newData = {
                'city': [results['city']],
                'country': [results['country']],
                
                'unit': [results['parameters'][0]['parameter']],
                'last_value': [results['parameters'][0]['lastValue']],

                'lat': [results['coordinates']['latitude']],
                'lng': [results['coordinates']['longitude']]
            }
            
            ti.xcom_push(key='ResultData', value=newData)
            return newData
        
        except IndexError as e:
            return f'{e}\nPlease check key results.'

# TODO 2: TRANSFORMATION
def transformation(**kwargs):
    import pandas as pd

    """ Initialize Task Instance """
    ti = kwargs['ti']
    resultExtract = ti.xcom_pull(key='ResultData', task_ids='Extract')

    """ DATAFRAME """
    dt = pd.DataFrame(resultExtract)

    """ TRANSFORMATION """
    # Cleaning Data
    dt['city'] = dt['city'].str.strip()
    dt['country'] = dt['country'].str.strip()
    dt['unit'] = dt['unit'].str.strip()

    # Change data type
    dt['last_value'] = dt['last_value'].astype(float)
    dt['lat'] = dt['lat'].astype(float)
    dt['lng'] = dt['lng'].astype(float)

    ti.xcom_push(key='Transformed', value=dt)
    return dt


""" CHECK RESPONSE """
def checkResponse(**kwargs):
    ti = kwargs['ti']
    resultResponse = ti.xcom_pull(key='ResultData', task_ids='Extract')

    logger.info(f'Data Found: {resultResponse}')

    if resultResponse is not None:
        return 'Transform'
    else:
        logger.info(f'Data Not Found: {resultResponse.status_code} - {resultResponse.reason}')
        return 'Error_Response'


# TODO 3: DISTRIBUTION TO DATABASE
def createTableSQL(**kwargs):
    """ Initialize Params """
    nameOfTABLE = kwargs['TableName']

    """ Initialize Task Instance """
    ti = kwargs['ti']

    """ GET COLUMNS """
    city = 'city'
    country = 'country'
    unit = 'unit'
    last_value = 'last_value'
    lat = 'lat' 
    lng = 'lng'

    createQuery = f"""
        CREATE TABLE {nameOfTABLE} (
            id serial primary key, 
            {city} varchar(250),
            {country} varchar(250), 
            {unit} varchar(20), 
            {last_value} float8, 
            {lat} float8,
            {lng} float8
        )
    """

    try:
        """ Create Connection """
        connDB = PostgresHook(postgres_conn_id='neonServerDB-Postgres').get_conn()
        cursor = connDB.cursor()

        cursor.execute(createQuery)
        
        connDB.commit()
        connDB.close()

    except errors.DuplicateTable:
        logging.info(f'Table {nameOfTABLE} Already Exist')


    ti.xcom_push(key='Create', value=createQuery)

    return createQuery

# TODO 4: DISTRIBUTION TO DATABASE
def insertValues(**kwargs):
    """ Initialize Params """
    nameOfTABLE=kwargs['TableName']
    
    """ Initialize Task Instance """
    ti = kwargs['ti']
    resultTransformation = ti.xcom_pull(key='Transformed', task_ids='Transform')
    print(resultTransformation.dtypes)
    result = resultTransformation.to_dict(orient='records')

    insertVal = f"""
        INSERT INTO {nameOfTABLE} (city, country, unit, last_value, lat, lng) \
            VALUES (
                '{result[0]['city']}', 
                '{result[0]['country']}', 
                '{result[0]['unit']}', 
                '{result[0]['last_value']}', 
                '{result[0]['lat']}', 
                '{result[0]['lng']}'
                )"""

    """ Create Connection """
    connDB = PostgresHook(postgres_conn_id='neonServerDB-Postgres').get_conn()
    cursor=connDB.cursor()

    """ Insert Data """
    cursor.execute(insertVal)
    connDB.commit()


""" CHECK TABLE EXIST """
def checkTable(**kwargs):
    ti = kwargs['ti']
    resultCreateTable = ti.xcom_pull(key='Create', task_ids='Create_Table')

    if resultCreateTable is not None:
        logging.info(f'Table Created: {resultCreateTable}')
        return 'Insert_Data'
    else:
        return 'Insert_Data'


logger = logging.getLogger(__name__)

""" Initialize Variables Required """
ENDPOINT = Variable.get('endpoint')
API_KEY = Variable.get('api_key')
SQL_QUERY = Variable.get('show_records')
tableNAME = 'air_quality'

COUNTRY = 'ID'
CITY = 'Jakarta'

""" PARAMS & HEADER"""
params = {
    'country':COUNTRY,
    'city':CITY
}

headers = {
    'X-API-Key':API_KEY,
    'accept': 'application/json'
}

""" DATETIME """
date = datetime.now()

startDate = datetime(2023, 11, 22)
endDate = date.strftime("%Y-%m-%d %H:%M:%S")
testDate = datetime(2023, 12, 13)

timeCron = '0 4 * * 0-7'

""""" DEFAULT ARGS """
default_args = {
    'owner': 'ghifari',
    'start_date': startDate,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'end_date': endDate,
}


""" DAG with all TASKS """
airQuality = DAG(
    dag_id='air_quality',
    default_args=default_args,
    schedule_interval=timeCron,
    catchup=True,
    fail_stop=True
)

""" EXTRACT TASK """
Extract = PythonOperator(
    task_id='Extract',
    python_callable=fetch_urlCities,
    provide_context=True,
    op_kwargs={
        'url': ENDPOINT,
        'params': params,
        'headers': headers
    },
    dag=airQuality
)

""" CHECKING RESPONSE TASK """
conditionResponse = BranchPythonOperator(
    task_id='Check_Response',
    python_callable=checkResponse,
    dag=airQuality
)

""" DUMMY ERROR RESPONSE TASK """
errorResponse= DummyOperator(
    task_id='Error_Response',
    dag=airQuality
)

""" TRANSFORMATION TASK """
Transformation = PythonOperator(
    task_id='Transform',
    python_callable=transformation,
    provide_context=True,
    dag=airQuality
)

""" CREATE TABLE TASK """
createTable = PythonOperator(
    task_id='Create_Table',
    python_callable=createTableSQL,
    provide_context=True,
    op_kwargs={
        'TableName': tableNAME
    },
    dag=airQuality
)

""" CHECK TABLE EXIST TASK """
conditionTable = BranchPythonOperator(
    task_id='CheckTable',
    python_callable=checkTable,
    dag=airQuality
)


""" INSERT VALUES TASK """
insertINTO = PythonOperator(
    task_id='Insert_Data',  
    python_callable=insertValues,
    provide_context=True,
    op_kwargs={
        'TableName': tableNAME
    },
    dag=airQuality
)

""" FLOW DEPENDENCY """
Extract >> conditionResponse >> [Transformation, errorResponse]
Transformation >> createTable >> conditionTable >> insertINTO


""" LABELING TASK """
conditionResponse >> Label('Success') >> Transformation
conditionResponse >> Label('Error') >> errorResponse
conditionTable >> Label('Success') >> insertINTO