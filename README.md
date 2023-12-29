# Air Quality Data Processing with Apache Airflow

This repository contains the implementation of an Apache Airflow Directed Acyclic Graph (DAG) for processing air quality data. The DAG performs the following tasks:

1. **Data Extraction**: Ingests data from the [OpenAQ API](https://docs.openaq.org/docs) to retrieve information on the current air quality worldwide.

2. **Data Transformation**: Filters the retrieved data to include only information from Jakarta, Indonesia, and transforms it into a format suitable for storage in a database table.

3. **Database Interaction**: Creates a PostgreSQL connection and a new table to store the transformed air quality data.

4. **Scheduled Execution**: Schedules the DAG to run daily at 4 am.

## DAG Structure

The DAG consists of the following tasks:

- **Extract**: Retrieves air quality data from the OpenAQ API.
- **Check_Response**: Checks the response status and either proceeds with the transformation or goes to the error branch.
- **Error_Response**: Dummy task representing the error branch.
- **Transform**: Transforms the extracted data, preparing it for storage.
- **Create_Table**: Creates a new table in the PostgreSQL database.
- **CheckTable**: Checks if the table already exists and either proceeds with data insertion or goes to the next task.
- **Insert_Data**: Inserts the transformed data into the PostgreSQL database.

## How to Run

1. docker compose up.
2. Configure Airflow to connect to your PostgreSQL database.
3. Trigger the DAG manually or wait for the scheduled run.

Feel free to customize and extend this DAG based on your specific requirements.

---

*Note: Make sure to replace placeholder texts, such as database connection details and API keys, with your actual information.*
