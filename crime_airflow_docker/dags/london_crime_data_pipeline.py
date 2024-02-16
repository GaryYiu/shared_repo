import json
from datetime import timedelta, datetime

from airflow import DAG
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.http.operators.http import SimpleHttpOperator

from airflow.contrib.operators.bigquery_operator import BigQueryOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.contrib.operators.bigquery_check_operator import BigQueryCheckOperator

from airflow.macros import ds_format, ds_add

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,    
    'start_date': datetime(2022, 3, 16),
    'email': ['airflow@airflow.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 5,
    'retry_delay': timedelta(minutes=5),
}

# Set Schedule: Run pipeline once a day. 
# Use cron to define exact time. Eg. 8:15am would be "15 08 * * *"
schedule_interval = "0 12 16 * *"

# Define DAG: Set ID and assign default args and schedule interval
with DAG(
    'london_crime_data_pipeline',
    start_date=datetime(2022, 3, 16),
    schedule_interval=schedule_interval,
    default_args=default_args,
    max_active_runs=1,
    template_searchpath="/opt/airflow/dags/sql",
    catchup=True,
) as dag:

    # Config variables
    BQ_CONN_ID = "my_gcp_conn"
    BQ_PROJECT = "gary-yiu-001"
    BQ_DATASET = "london"

    ## Task 2: trigger the cloud function to fetch crime data  
    trigger_cloud_function = SimpleHttpOperator(
            task_id='trigger_cloud_function',
            http_conn_id='my_gcp_conn',  # Airflow connection ID for HTTP
            endpoint='<cloud-function-endpoint>/download_crime_data/?date={{ ds }}',
            method='POST',
            headers={"Content-Type": "application/json", "extra__google_cloud_platform__num_retries": "6"},
            response_check=lambda response: response.status_code == 200
        )

    ## Task 3: load the downloaded csv into the BigQuery table
    load_csv_to_bigquery = GCSToBigQueryOperator(
            task_id='load_csv_to_bigquery',
            gcp_conn_id='my_gcp_conn',
            bucket='gary-yiu-001-bucket',  # Replace with your GCS bucket name
            source_objects=['crime-metropolitan-street.csv'],  # Replace with the path to your CSV file in the bucket
            destination_project_dataset_table='{0}.{1}.london_recent_crime_data_raw'.format(
                BQ_PROJECT, BQ_DATASET
            ),  # Replace with your BigQuery table reference
            create_disposition='CREATE_IF_NEEDED',  # Create the table if it doesn't exist
            write_disposition='WRITE_TRUNCATE',  # Overwrite the table if it already exists
            skip_leading_rows=1,  # Skip the header row
            source_format='CSV',
            autodetect=True,  # Automatically detect the schema from the CSV file
        )

    ## Task 4: fetch and clean the raw data from the london_recent_crime_data_raw table and insert the data to the staging dataset
    cleaning_crime_data_insert = BigQueryOperator(
            task_id='cleaning_crime_data_insert',
            sql='london_crime_data_cleaned.sql',
            destination_dataset_table=f"{ BQ_PROJECT }.{ BQ_DATASET }.london_recent_crime_data$" + "{{ ds_nodash[:6] }}",    
            write_disposition='WRITE_TRUNCATE',
            create_disposition='CREATE_IF_NEEDED',
            allow_large_results=True,
            use_legacy_sql=False,
            time_partitioning={"type": "MONTH", "field": "date_month"},
            cluster_fields="lsoa_code",
            gcp_conn_id=BQ_CONN_ID,
            dag=dag
        )

    ## Task 5: aggregate data into final table
    aggregate_data_with_polygon = BigQueryOperator(
            task_id='aggregate_data_with_polygon',
            sql='london_crime_data_joined_polygon.sql',
            destination_dataset_table=f'{BQ_PROJECT}.{BQ_DATASET}.london_crime_data_agg',    
            write_disposition='WRITE_TRUNCATE',
            allow_large_results=True,
            use_legacy_sql=False,
            gcp_conn_id=BQ_CONN_ID,
            dag=dag
        )

    # Task 6: Check if agg data is written successfully
    check_agg_data = BigQueryCheckOperator(
        task_id='check_agg_data',
        sql='''
        SELECT
            COUNT(*) AS rows_in_partition
        FROM `{0}.{1}.london_crime_data_agg`
        '''.format(BQ_PROJECT, BQ_DATASET
            ),
        use_legacy_sql=False,
        gcp_conn_id=BQ_CONN_ID,
        dag=dag)

    # Setting up Dependencies
    trigger_cloud_function >> load_csv_to_bigquery >> cleaning_crime_data_insert >> aggregate_data_with_polygon >> check_agg_data
