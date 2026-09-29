from pymongo import MongoClient

MONGO_URI = "mongodb+srv://202401202_db_user:01ZowsBz25dUkVi3@aisoftwareanalyzer.1urpvf3.mongodb.net/?appName=AiSoftwareAnalyzer"

client = MongoClient(MONGO_URI)

db = client["project_health"]

users_collection = db["users"]
projects_collection = db["projects"]
commits_collection = db["commits"]
pull_requests_collection = db["pull_requests"]
issues_collection = db["issues"]
sprints_collection = db["sprints"]
flags_collection = db["flags"]
reports_collection = db["reports"]
integration_credentials_collection = db["integration_credentials"]
org_settings_collection = db["org_settings"]
audit_logs_collection = db["audit_logs"]

print("MongoDB connected successfully!")

