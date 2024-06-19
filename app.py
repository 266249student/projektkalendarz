from flask import Flask, render_template, request
import psycopg2
from azure.storage.blob import BlobServiceClient
import requests
import base64
import hmac
import hashlib
import time
from urllib.parse import quote_plus, urlencode

app = Flask(__name__)

# PostgreSQL connection parameters
params = {
    'dbname': 'databasemoje',
    'user': 'postgres',
    'password': 'Hasloadmin123!',
    'host': 'serveraplikacji.postgres.database.azure.com',
    'port': '5432'
}

# Azure Blob Storage connection parameters
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=blobstoragedlaproj;AccountKey=DefaultEndpointsProtocol=https;AccountName=blobstoragedlaproj;AccountKey=UYKMFQEAJnvwUyNjRixZDCahrfaaGiFqu2WVFsWB8OLeU3MsRP83W58H9hLpyhhuBQ3buXOSSVHT+ASt/G/rBw==;EndpointSuffix=core.windows.net=;EndpointSuffix=core.windows.net"
AZURE_STORAGE_CONTAINER_NAME = "blobstoragedlaproj"

# Azure Notification Hub connection parameters
NOTIFICATION_HUB_NAME = "powiadomieniaproj"
NOTIFICATION_HUB_NAMESPACE = "powiadomieniaproj"
NOTIFICATION_HUB_SAS_KEY_NAME = "RootManageSharedAccessKey"
NOTIFICATION_HUB_SAS_KEY_VALUE = "Endpoint=sb://powiadomieniaproj.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=XlSkQZfl/1pHSswc2+ii+ZzhMtdlSg1qfeYarJoWnMA="


# Function to establish PostgreSQL connection
def connect():
    conn = psycopg2.connect(**params)
    return conn


# Function to upload file to Azure Blob Storage
def upload_to_azure_storage(file_stream, file_name):
    try:
        # Create BlobServiceClient using the connection string
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Get container client
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)

        # Upload file
        blob_client = container_client.upload_blob(name=file_name, data=file_stream)

        return True, blob_client.url  # Return True for success and URL of the uploaded blob
    except Exception as e:
        print(f"Error uploading to Azure Blob Storage: {str(e)}")
        return False, None


# Function to generate SAS token for Azure Notification Hub
def generate_sas_token(uri):
    expiry = int(time.time() + 3600)
    string_to_sign = quote_plus(uri) + '\n' + str(expiry)
    signature = base64.b64encode(hmac.new(
        base64.b64decode(NOTIFICATION_HUB_SAS_KEY_VALUE),
        string_to_sign.encode('utf-8'),
        hashlib.sha256).digest()).decode('utf-8')
    return 'SharedAccessSignature sr={}&sig={}&se={}&skn={}'.format(
        quote_plus(uri), quote_plus(signature), expiry, NOTIFICATION_HUB_SAS_KEY_NAME)


# Function to send notification to Azure Notification Hub
def send_notification(message):
    uri = 'https://{}.servicebus.windows.net/{}/messages'.format(NOTIFICATION_HUB_NAMESPACE, NOTIFICATION_HUB_NAME)
    sas_token = generate_sas_token(uri)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': sas_token,
        'ServiceBusNotification-Format': 'template'
    }
    payload = {
        "data": {
            "message": message
        }
    }
    try:
        response = requests.post(uri, headers=headers, json=payload)
        response.raise_for_status()
        print("Notification sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Error sending notification: {str(e)}")


@app.route('/')
def index():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tabela1;")
    rows = cur.fetchall()
    conn.close()
    return render_template('index.html', rows=rows)


@app.route('/add', methods=['POST'])
def add():
    conn = connect()
    cur = conn.cursor()
    day = request.form['day']  # Assuming the form field name for day is 'day'
    note = request.form['note']  # Assuming the form field name for note is 'note'
    course = request.form['course']
    cur.execute("INSERT INTO tabela1 (day, note, course) VALUES (%s, %s, %s);", (day, note, course))
    conn.commit()
    conn.close()

    # Send notification
    message = f"New record added: {day} - {note} - {course}"
    send_notification(message)

    return 'Record successfully added'


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part in the form!'

    file = request.files['file']
    if file.filename == '':
        return 'No selected file!'

    # Call function to upload file to Azure Blob Storage
    success, blob_url = upload_to_azure_storage(file.stream, file.filename)

    if success:
        # Send notification
        message = f"File successfully uploaded: {file.filename}"
        send_notification(message)
        return f'File successfully uploaded to Azure Blob Storage! <br> Blob URL: {blob_url}'
    else:
        return 'Failed to upload file to Azure Blob Storage.'


if __name__ == '__main__':
    app.run(debug=True)
