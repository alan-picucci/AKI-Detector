# Acute Kidney Injury Detector - 70102-Kensington Palace (aka. Alameda)

## Description
The Acute Kidney Injury Detector is a system designed to read a real-time stream of patient and medical test data, detect cases of AKI (Acute Kidney Injury), and report positive cases to the pager system of the urgency care team. The system achieves this objective by reading and parsing two streams of HL7 messages over the MLLP protocol, predicting AKI cases using a pre-trained model based on patient demographics and creatinine levels in the blood, and reporting positive cases to the pager system through an HTTP request. The system is optimized for minimal latency, with a hard constraint of 3 seconds.

## Table of Contents
- [Model Details](#model-details)
- [Database Structure](#database-structure)
- [Local test execution](#local-test-execution)
- [Running inference with Docker](#running-inference-with-docker)
- [Members](#members)

## Model Details
The primary model is a Random Forest which utilizes the following features:
1. Age
2. Sex
3. Latest creatinine result
4. Mean creatinine result
5. Minimum creatinine result

An alternative model has been trained excluding age and sex for scenarios lacking demographic data.

## Database Structure

The AKI Detection System utilizes a SQLite database to store and manage patient data and blood test results. The database consists of the following tables:

1. **Patients**: Stores patient demographic information and AKI risk assessment metrics.
   - `MRN` (INTEGER): Medical Record Number, primary key.
   - `Sex` (TEXT): Gender of the patient.
   - `DOB` (DATE): Date of birth.
   - `Paged` (INTEGER): Indicator (0 or 1) if a patient has been paged due to high AKI risk. If so, we do not page them again in the future.
   - `MinTestResult` (REAL): Minimum creatinine level from recorded tests.
   - `MeanTestResult` (REAL): Average creatinine level from recorded tests.
   - `TestCount` (INTEGER): Total number of creatinine tests conducted.

2. **BloodTests**: Records individual blood test results for each patient.
   - `TestID` (INTEGER): Unique identifier for the blood test, primary key.
   - `MRN` (INTEGER): Medical Record Number, foreign key linked to the Patients table.
   - `TestDate` (DATE): Date when the blood test was conducted.
   - `TestResult` (REAL): Creatinine level from the blood test.

Relationships:
- Each record in the `BloodTests` table is linked to a record in the `Patients` table through the `MRN` field.
- The `Patients` table aggregates data for AKI risk assessment based on individual records from the `BloodTests` table.


## Local test execution

Follow these steps to execute tests locally without Docker:

1. Open your terminal and navigate to the root directory of the project:

    ```shell
    cd /path/to/project
    ```

2. Execute the test script. If you are using `zsh`, type:

    ```shell
    zsh test.sh
    ```

    If you are using `bash`, type:

    ```shell
    sh test.sh
    ```

*Note:* Tests are configured to run automatically during the build process.

## Running inference with Docker
1. Clone the repository.
2. Build the Docker image:

    ```shell
    docker build -t inference . --build-arg local=data --build-arg dir=state
    ```
3. Run the container:
    ```shell
    docker run inference
    ```

The running client will try to connect to ports 8440 for MLLP and 8441 for pager systems. Customize these ports through environment variables, if necessary:
```shell
docker run --env MLLP_ADDRESS=host.docker.internal:8440 --env PAGER_ADDRESS=host.docker.internal:8441 inference
```

### Build with Test Outputs

To build the Docker image locally and see test outputs in plain text:

1. Navigate to the project's root directory:

    ```shell
    cd /path/to/project
    ```

2. Execute the Docker build command with test output settings:

    ```shell
    docker build --no-cache --progress=plain -t inference . --build-arg local=data --build-arg dir=state
    ```

## Members
- George Duffy (@gd1223)
- Alan Picucci (@ap3423)
- Simon Rendon Arango (@sr923)
- Ivaylo Stoyanov (@iis23)

