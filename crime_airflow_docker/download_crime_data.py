import functions_framework
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import json
import zipfile
import os
from google.cloud import storage

##function to fetch data from authority
@functions_framework.http
def download_and_upload_data(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    run_date = request.args.get('date')

    # Step 1: Send a GET request to the custom download page URL
    headers = {
        'Referer': 'https://data.police.uk/data/'
    }

    response = requests.get("https://data.police.uk/data/", headers=headers)

    if response.status_code == 200:
        # Step 2: Parse HTML content and locate the form
        soup = BeautifulSoup(response.content, "html.parser")
        form = soup.find("form")

        # Step 3: Extract the CSRF token from the response cookies
        csrf_token = response.cookies.get('csrftoken')

        current_date = datetime.strptime(run_date, '%Y-%m-%d')
        minus_one_month = (current_date - timedelta(days=30)).strftime("%Y-%m")
        print('Input date minus one month is ' + minus_one_month)

        # Step 4: Extract form data including hidden fields or required parameters
        form_data = {
            "csrfmiddlewaretoken": csrf_token,
            'date_from': minus_one_month,
            'date_to': minus_one_month,
            'forces': ['metropolitan'],
            'include_crime': 'on'
            # Add any other required form fields
        }

        # Step 5: Simulate form submission by sending a POST request with CSRF cookie
        submit_url = "https://data.police.uk/data/"
        cookies = {
            'csrftoken': csrf_token
        }
        response = requests.post(submit_url, data=form_data, headers=headers, cookies=cookies, allow_redirects=False)
        
        if response.status_code == 302:
            # Step 6: Retrieve refreshed page locatoin after form submission
            location = response.headers.get('location')
            print(location)
            # Step 7: Retrieve the session ID from the location and access the progress page for the download URL
            substring_to_remove = "/data/fetch/"
            result_string = location.replace(substring_to_remove, "")

            redirected_response = requests.get("https://data.police.uk/data/progress/" + result_string)
            
            download_url = None

            # Step 8: Extract the download URL from the JSON response
            refreshed_page_content = redirected_response.content.decode('utf-8')
            print(refreshed_page_content)
            refreshed_page_json = json.loads(refreshed_page_content)
            print(refreshed_page_json)
            download_url = refreshed_page_json['url']
            print(download_url)

            # Step 9: Download the file
            if download_url:
                response = requests.get(download_url)
                if response.status_code == 200:
                    file_name = "crime_data_metropolitan.zip"  # Adjust the file name if needed
                    with open(file_name, "wb") as file:
                        file.write(response.content)
                    print("Metropolitan Police crime data downloaded successfully.")
                    # Step 10: Unzip the file
                    with zipfile.ZipFile(file_name, 'r') as zip_ref:
                        zip_ref.extractall()

                    # Step 11: Move the CSV file to desired location
                    extracted_file_name = minus_one_month + "-metropolitan-street.csv" # Adjust the file name if needed
                    renamed_file_name = "crime-metropolitan-street.csv"
                    os.rename(minus_one_month + "/" + extracted_file_name, renamed_file_name)  # Move the file to the desired location

                    print("CSV file extracted and saved successfully.")

                    # Step 12: Upload the CSV file to a GCS bucket
                    bucket_name = 'gary-yiu-001-bucket'  # Replace with your GCS bucket name
                    file_path = renamed_file_name  # Path to the CSV file
                    destination_blob_name = 'crime-metropolitan-street.csv'  # Desired path and filename in the bucket

                    storage_client = storage.Client()
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(destination_blob_name)
                    blob.upload_from_filename(file_path)

                    print("CSV file uploaded to Google Cloud Storage successfully.")
                else:
                    print("Failed to download Metropolitan Police crime data.")
                    return make_response("Failed to download Metropolitan Police crime data.", 500)
            else:
                print("Download URL not found.")
                return make_response("Download URL not found.", 500)
        else:
            print("Form submission failed.")
            return make_response("Form submission failed.", 500)
    else:
        print("Failed to access the custom download page.")
        return make_response("Failed to access the custom download page.", 500)
    return "Process completed successfully."
