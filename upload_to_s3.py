import os
import boto3

def upload_file():
    bucket_name = 'spesti-grocery-data-46367c80'
    file_name = 'products.json'
    
    # Configure boto3 client with the known region
    s3 = boto3.client('s3', region_name='eu-central-1')
    
    print(f"Uploading {file_name} to bucket {bucket_name}...")
    
    s3.upload_file(
        Filename=os.path.join(os.getcwd(), file_name),
        Bucket=bucket_name,
        Key=file_name,
        ExtraArgs={
            'ContentType': 'application/json'
        }
    )
    
    print("Upload complete! File available at: " +
          f"https://{bucket_name}.s3.eu-central-1.amazonaws.com/{file_name}")

if __name__ == "__main__":
    upload_file()
