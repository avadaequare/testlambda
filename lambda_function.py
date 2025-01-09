import boto3
import os
import paramiko  # Ensure this is included in your deployment package

# AWS Clients
ec2 = boto3.client('ec2')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    # Retrieve private key from environment variable
    private_key_content = os.environ.get("PRIVATE_KEY")
    if not private_key_content:
        return {"error": "PRIVATE_KEY environment variable is not set."}

    # Write the private key content to a temporary file
    key_file_path = "/tmp/private-key.pem"
    try:
        with open(key_file_path, "w") as key_file:
            key_file.write(private_key_content)
        os.chmod(key_file_path, 0o400)  # Set permissions to read-only
    except Exception as e:
        return {"error": f"Failed to write private key to temporary file: {str(e)}"}

    # Process the action from the event
    action = event.get("action", "").lower()
    if action == "start_ec2":
        return start_ec2_instances(event)
    elif action == "stop_ec2":
        return stop_ec2_instances(event)
    elif action == "upload_file":
        return upload_file_to_s3(event, key_file_path)
    elif action == "download_file":
        return download_file_from_s3(event, key_file_path)
    else:
        return {"message": "Invalid action. Use start_ec2, stop_ec2, upload_file, or download_file."}

def start_ec2_instances(event):
    instance_ids = event.get("instance_ids", [])
    if not instance_ids:
        return {"message": "Instance IDs not provided."}
    response = ec2.start_instances(InstanceIds=instance_ids)
    return {"message": f"Starting instances: {instance_ids}", "response": response}

def stop_ec2_instances(event):
    instance_ids = event.get("instance_ids", [])
    if not instance_ids:
        return {"message": "Instance IDs not provided."}
    response = ec2.stop_instances(InstanceIds=instance_ids)
    return {"message": f"Stopping instances: {instance_ids}", "response": response}

def upload_file_to_s3(event, key_file_path):
    server_ip = event.get("server_ip")
    username = event.get("username")
    local_file_path = event.get("local_file_path")
    s3_bucket = event.get("s3_bucket")
    s3_key = event.get("s3_key", os.path.basename(local_file_path))
    
    if not all([server_ip, username, local_file_path, s3_bucket]):
        return {"message": "Missing parameters for file upload."}
    
    try:
        # SSH and SFTP logic
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=server_ip, username=username, key_filename=key_file_path)
        
        sftp = ssh.open_sftp()
        sftp.get(local_file_path, f"/tmp/{os.path.basename(local_file_path)}")
        sftp.close()
        ssh.close()
        
        # Upload file to S3
        s3.upload_file(f"/tmp/{os.path.basename(local_file_path)}", s3_bucket, s3_key)
        return {"message": f"File uploaded to S3 bucket {s3_bucket} with key {s3_key}"}
    except Exception as e:
        return {"error": str(e)}

def download_file_from_s3(event, key_file_path):
    server_ip = event.get("server_ip")
    username = event.get("username")
    s3_bucket = event.get("s3_bucket")
    s3_key = event.get("s3_key")
    remote_file_path = event.get("remote_file_path")
    
    if not all([server_ip, username, s3_bucket, s3_key, remote_file_path]):
        return {"message": "Missing parameters for file download."}
    
    try:
        # Download file from S3
        s3.download_file(s3_bucket, s3_key, f"/tmp/{os.path.basename(remote_file_path)}")
        
        # SSH and SFTP logic
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=server_ip, username=username, key_filename=key_file_path)
        
        sftp = ssh.open_sftp()
        sftp.put(f"/tmp/{os.path.basename(remote_file_path)}", remote_file_path)
        sftp.close()
        ssh.close()
        
        return {"message": f"File {s3_key} downloaded from S3 bucket {s3_bucket} to server {remote_file_path}"}
    except Exception as e:
        return {"error": str(e)}
